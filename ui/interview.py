"""Explicit actions keep recording, confirmation and evaluation separate."""
import hashlib
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

from core.interview import MODES, Interviews, Session, Turn, QuestionPlan, confirm, advance, evaluate, report
from core.material import topics
from core.speech import transcribe
from ui.claims import open_claims
from ui.common import download
from ui.plan import jump_to
from ui.practice import feedback_display


player = components.declare_component("crackmate_question_player", path=str(Path(__file__).parent / "speech_player"))


def cleanup(session_id):
    st.session_state["interview_cleanup"] = session_id


def setup(app, repository):
    with st.expander("Start an interview", expanded=not repository.list(app.record.id)):
        with st.form("interview-setup"):
            mode=st.selectbox("Interview mode",MODES)
            topic=st.selectbox("Interview topic",topics(app.profile))
            project=st.selectbox("Interview project",[""]+[p.id for p in app.profile.projects],
                                 format_func=lambda value: next((p.title for p in app.profile.projects if p.id==value),"No project"))
            difficulty=st.selectbox("Interview difficulty",["Basics","Intermediate","Advanced"])
            budget=st.number_input("Question budget (follow-ups count)",min_value=1,max_value=10,value=5)
            coach=st.radio("Feedback timing",["Coach","Simulation"])=="Coach"
            spoken=st.checkbox("Enable spoken questions")
            weak=st.text_input("Areas to focus on",max_chars=1000)
            claims=open_claims(app)
            probe=bool(claims) and st.checkbox(f"Probe my {len(claims)} undefended resume claims (from Claim Checker)",value=True)
            st.caption("English. Audio is sent to Groq for transcription. Only explicitly confirmed answers are evaluated by Groq. Stop playback before recording.")
            consent=st.checkbox("I understand and want to start")
            start=st.form_submit_button("Start interview",disabled=not app.settings.api_key)
        if start:
            if not consent:
                st.error("Confirm the provider disclosure before starting.")
                return
            if mode=="Project deep-dive" and not project:
                st.error("Select a project for this mode.")
                return
            if mode == "DSA reasoning":
                topic = "Data structures and algorithms"
            elif mode == "System design":
                topic = "System design fundamentals"
            def create(progress):
                context={
                    "mode":mode,"topic":topic,"difficulty":difficulty,"count":budget,
                    "weak_areas":weak,"role":app.profile.role,"company":app.profile.company,
                    "project":[p.model_dump(exclude={"id","reference"}) for p in app.profile.projects if p.id==project],
                    "claims_to_probe":claims if probe else [],
                    "completed_lessons":[i.title for i in app.store.items(app.record.id) if app.store.completed(app.record.id,i)],
                }
                def validate(plan):
                    if len(plan.questions)!=budget or len({q.question for q in plan.questions})!=budget:
                        raise ValueError("Return the requested number of distinct questions.")
                plan,_=app.service.generate("interview_plan",context,QuestionPlan,validate=validate,progress=progress)
                session=Session(profile_id=app.record.id,mode=mode,topic=topic,project_id=project,
                                difficulty=difficulty,budget=budget,coach=coach,spoken=spoken,
                                turns=[Turn(question=q) for q in plan.questions],context=context)
                repository.create(session)
                st.session_state["interview_target"]=session.id
                return True
            if app.action(create,"Preparing interview questions…"):
                st.rerun()


def render(app):
    cleanup_id = st.session_state.pop("interview_cleanup", None)
    if cleanup_id:
        for key in list(st.session_state):
            if key.startswith("voice:" + cleanup_id):
                del st.session_state[key]
    st.title("Interview Room")
    repository=Interviews(app.store)
    setup(app,repository)
    sessions=repository.list(app.record.id)
    if not sessions:
        st.info("Start a short mock interview. Typed answers are available throughout.")
        return
    target=st.session_state.pop("interview_target",None)
    if target:
        st.session_state["interview_selected"]=target
    ident=st.selectbox("Saved interview",[s.id for s in sessions],key="interview_selected",
                      format_func=lambda value:next(f"{s.mode} · {s.state} · {s.id[:6]}" for s in sessions if s.id==value))
    session=next(s for s in sessions if s.id==ident)

    def save():
        result=app.action(lambda _:repository.save(session))
        if result:
            st.rerun()

    st.caption(f"{session.mode} · {session.difficulty} · {'Immediate feedback' if session.coach else 'Feedback deferred'} · {session.state}")
    with st.expander("Session controls"):
        if session.state not in ("completed","abandoned","paused") and st.button("Pause interview"):
            session.resume_state=session.state
            session.state="paused"
            cleanup(session.id)
            save()
        if session.state=="paused" and st.button("Resume interview"):
            session.state=session.resume_state
            save()
        if session.state not in ("completed","abandoned") and st.button("End interview and view report"):
            session.state="completed"
            cleanup(session.id)
            save()
        if session.state not in ("completed","abandoned") and st.button("Abandon interview"):
            session.state="abandoned"
            cleanup(session.id)
            save()
        delete=st.checkbox("Permanently delete this interview")
        if st.button("Delete interview",disabled=not delete):
            repository.delete(session.id,app.record.id)
            cleanup(session.id)
            st.rerun()

    if session.state in ("completed","abandoned"):
        st.markdown(report(session))
        download("Download interview report",report(session),"crackmate-interview.md","interview-export")
        weakest=sorted((t for t in session.turns if t.feedback),
                       key=lambda t:sum(getattr(t.feedback,d).score for d in ("accuracy","coverage","reasoning","clarity")))[:3]
        if weakest:
            st.markdown("#### Study next from this interview")
        for turn in weakest:
            topic=turn.topic or session.topic
            level=turn.difficulty if turn.difficulty in ("Basics","Intermediate","Advanced") else "Basics"
            slot=f"project:{session.project_id}:Engineering decisions" if session.project_id else f"skill:{level}:{topic}"
            if st.button(f"Open lesson: {topic}",key=f"study:{turn.id}"):
                jump_to(slot)
        with st.expander("Relevant saved lessons"):
            for item in app.store.items(app.record.id):
                if item.kind in ("skill","project"):
                    st.write(item.title)
        return
    if session.state=="paused":
        st.info("Resume to continue. Confirmed transcripts and completed answers are saved.")
        return
    turn=session.turns[session.index]
    st.progress(session.index/session.budget,text=f"Question {session.index+1} of {session.budget}")
    st.subheader(turn.question.question)
    st.caption("Generated practice question. Follow-ups replace the next planned question and count toward the budget.")
    if session.spoken:
        player(question=turn.question.question,key="speaker:"+session.id)
    if not session.coach and st.button("Reveal feedback now and switch to coach mode"):
        session.coach=True
        save()
    prefix=f"voice:{session.id}:{turn.id}:{len(turn.retries)}"
    if session.state!="feedback ready":
        if st.button("Clarify this question"):
            turn.hint_used = True
            save()
        if turn.hint_used:
            st.info(turn.question.hint)
        recording=st.audio_input("Record answer",sample_rate=16000,key=prefix+":mic")
        upload=st.file_uploader("Or upload a PCM WAV answer",type=["wav"],max_upload_size=app.settings.audio_mb,key=prefix+":file")
        audio=recording or upload
        st.caption(f"Maximum {app.settings.audio_seconds} seconds and {app.settings.audio_mb} MB. If microphone access fails, type below.")
        if audio:
            data=audio.getvalue()
            digest=hashlib.sha256(data).hexdigest()
            if st.button("Discard recording"):
                cleanup(session.id)
                st.rerun()
            if st.button("Transcribe recording",disabled=not app.settings.api_key):
                if turn.recording_hash==digest and turn.original:
                    st.session_state[prefix+":edit"]=turn.original
                else:
                    text=app.action(lambda _:transcribe(data,app.settings),"Transcribing recording…")
                    if text:
                        turn.original=text
                        turn.recording_hash=digest
                        turn.confirmed=""
                        session.state="transcript review"
                        st.session_state[prefix+":edit"]=text
                        save()
        if prefix+":edit" not in st.session_state:
            st.session_state[prefix+":edit"]=turn.confirmed or turn.original
        text=st.text_area("Review transcript or type your answer",key=prefix+":edit",max_chars=3500,height=170)
        if turn.original:
            with st.expander("Original speech transcript"):
                st.text(turn.original)
        st.caption("Include a written outline or code here if helpful. Code is reviewed as text.")
        if st.button("Confirm answer",type="primary"):
            def confirmed(_):
                confirm(session,text)
                repository.save(session)
                return True
            if app.action(confirmed):
                cleanup(session.id)
                st.rerun()
        if turn.confirmed:
            st.success("Confirmed answer saved. Ready to evaluate.")
            if st.button("Evaluate confirmed answer",disabled=not app.settings.api_key):
                if app.action(lambda progress:evaluate(repository,app.service,app.record,session,progress),"Evaluating confirmed answer…"):
                    st.rerun()
        if st.button("I don’t know"):
            confirm(session,"I don't know.")
            repository.save(session)
            cleanup(session.id)
            st.rerun()
        if st.button("Skip question"):
            advance(session,skip=True)
            cleanup(session.id)
            save()
    else:
        if session.coach:
            feedback_display(turn.feedback, turn.question.kind=="behavioural")
            if st.button("Retry this question"):
                turn.retries.append(turn.feedback)
                turn.previous_answers.append(turn.confirmed)
                turn.feedback=None
                turn.confirmed=""
                turn.original=""
                turn.recording_hash=""
                turn.outcome="pending"
                session.state="question ready"
                cleanup(session.id)
                save()
        else:
            st.success("Answer saved. Feedback will appear when the interview ends.")
        follow=st.checkbox("Use an adaptive follow-up next",value=True,disabled=turn.depth>0 or session.index+1>=session.budget)
        if st.button("Next question",type="primary"):
            advance(session,follow=follow)
            cleanup(session.id)
            save()
