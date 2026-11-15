"""Offline learning dashboard, catalogue editor and explicit plan proposals."""
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import streamlit as st

from core.learning import Learning, readiness, utcnow, export_progress, topic_id
from core.export import parse_item
from core.material import lesson_requests
from core.interview import Interviews, Session, Turn, PlannedQuestion
from ui.common import download
from ui.plan import jump_to


def render(app):
    st.title("Learning Progress")
    now=utcnow()
    learning=Learning(app.store,app.record.id)
    learning.sync()
    progress=learning.progress(now)
    settings=learning.settings()
    assessed=sum(t["count"]>0 for t in progress)
    st.caption(f"{assessed} topics assessed · {len(progress)-assessed} unassessed · "
               f"{sum(t['state']=='Due for review' for t in progress)} reviews due")
    st.caption("Progress uses local evidence. Lesson completion alone does not establish understanding.")
    overall,assessed_count,total,scores=readiness(progress)
    if overall is None:
        st.info("No readiness score yet. Answer practice questions or run a mock interview to get one.")
    else:
        st.metric("Overall readiness",f"{overall} / 100",f"{assessed_count} of {total} topics assessed",delta_color="off")
        st.caption("A coaching estimate from your latest scored answers. Hints, reveals and retries cap a topic at 70, "
                   "and topics you have not practised are not counted.")
        with st.expander("Readiness by topic"):
            ranked=sorted((s,t["name"]) for t in progress if (s:=scores[t["id"]]) is not None)
            st.dataframe([{"Topic":name,"Readiness":score} for score,name in ranked],hide_index=True)
    section=st.radio("Learning view",["Study next","Topic progress","Topic catalogue","Adaptive plan","Diagnostic","Compare attempts"],horizontal=True)
    if section=="Study next":
        minutes=st.number_input("Study minutes available now",min_value=5,max_value=240,value=30,step=5)
        queue=learning.queue(now,minutes)
        if not queue:
            st.info("No activities fit your current choices. Review postponed or dismissed topics below.")
        for item in queue:
            with st.container(border=True):
                st.subheader(item["name"])
                st.write(f"{item['activity']} · {item['duration']} min")
                st.caption(item["reason"])
                open_col,pin_col,later_col,dismiss_col=st.columns(4)
                if open_col.button("Open lesson",key="open:"+item["topic"]):
                    jump_to("skill:Basics:"+item["name"])
                if pin_col.button("Pin",key="pin:"+item["topic"]):
                    learning.preference("queue:"+item["topic"],{"pinned":True})
                    st.rerun()
                if later_col.button("Tomorrow",key="later:"+item["topic"]):
                    learning.preference("queue:"+item["topic"],{"postpone":(now.astimezone(ZoneInfo(settings["timezone"])).date()+timedelta(days=1)).isoformat()})
                    st.rerun()
                if dismiss_col.button("Dismiss",key="dismiss:"+item["topic"]):
                    learning.preference("queue:"+item["topic"],{"dismissed":True})
                    st.rerun()
        if st.button("Restore dismissed and postponed recommendations"):
            for topic in progress:
                learning.preference("queue:"+topic["id"],{})
            st.rerun()
    elif section=="Topic progress":
        ident=st.selectbox("Topic",[t["id"] for t in progress],format_func=lambda i:next(t["name"] for t in progress if t["id"]==i))
        topic=next(t for t in progress if t["id"]==ident)
        st.subheader(topic["state"])
        st.write(f"Compatible attempts · {topic['count']} · Next review · {topic['due'] or 'not scheduled'}")
        st.caption(topic["limitation"])
        for evidence in topic["evidence"]:
            with st.expander(evidence["question"]):
                st.json(evidence)
        if st.button("Review tomorrow"):
            learning.preference("due:"+ident,(now.astimezone(ZoneInfo(settings["timezone"])).date()+timedelta(days=1)).isoformat())
            st.rerun()
        confirm=st.checkbox("Reset learning progress for this topic while preserving original practice history")
        if st.button("Reset topic progress",disabled=not confirm):
            learning.preference("reset:"+ident,now.isoformat())
            learning.preference("due:"+ident,None)
            st.rerun()
        confirm_schedule=st.checkbox("Reset this topic’s review date to today")
        if st.button("Reset review schedule",disabled=not confirm_schedule):
            learning.preference("due:"+ident,now.astimezone(ZoneInfo(settings["timezone"])).date().isoformat())
            st.rerun()
    elif section=="Topic catalogue":
        catalogue(learning,app)
    elif section=="Adaptive plan":
        plans(learning,app,now)
    elif section=="Diagnostic":
        diagnostic(learning,app)
    else:
        compare(learning)
    download("Download learning report",export_progress(learning,now),"crackmate-learning.md","learning-export")


def catalogue(learning,app):
    topics=learning.topics()
    lookup={t["id"]:t for t in topics}
    ident=st.selectbox("Edit topic",["new"]+list(lookup),format_func=lambda value:lookup[value]["name"] if value in lookup else "Add topic")
    topic=lookup.get(ident,dict(name="",description="",category="Custom",prerequisites=[],skills=[],levels=["Basics","Intermediate","Advanced"],role=""))
    with st.form("topic-editor"):
        name=st.text_input("Topic name",topic["name"],max_chars=200)
        description=st.text_area("Topic description",topic["description"],max_chars=1000)
        category=st.text_input("Category",topic["category"],max_chars=100)
        prerequisites=st.multiselect("Prerequisite topics",list(lookup),default=topic["prerequisites"],format_func=lambda value:lookup[value]["name"])
        skills=st.text_input("Related skills (comma separated)",", ".join(topic["skills"]))
        role=st.text_input("Role relevance (optional)",topic["role"],max_chars=200)
        if st.form_submit_button("Save topic"):
            result=app.action(lambda _:learning.save_topic(dict(
                id=uuid4().hex if ident=="new" else ident,name=name,description=description,category=category,
                prerequisites=prerequisites,skills=[s.strip() for s in skills.split(",") if s.strip()],
                levels=topic["levels"],role=role)) or True)
            if result: st.rerun()
    labels=set(e["label"] for e in learning.evidence())
    for group in app.profile.skills.model_dump().values():
        labels.update(group)
    if labels:
        label=st.selectbox("Skill or practice focus to map",sorted(labels))
        mapped=st.multiselect("Mapped topics",list(lookup),default=learning.mappings(label),format_func=lambda value:lookup[value]["name"],key="mapping:"+label)
        if st.button("Save mapping"):
            learning.remap(label,mapped)
            st.rerun()


def plans(learning,app,now):
    settings=learning.settings()
    lookup={t["id"]:t for t in learning.topics()}
    with st.form("learning-settings"):
        zone=st.text_input("Timezone",settings["timezone"])
        interview=st.text_input("Interview date (optional YYYY-MM-DD)",settings["interview"])
        daily=st.number_input("Study minutes per day",min_value=5,max_value=240,value=settings["daily_minutes"])
        length=st.number_input("Preferred block minutes",min_value=5,max_value=50,value=settings["session_minutes"])
        unavailable=st.text_area("Unavailable dates, one YYYY-MM-DD per line","\n".join(settings["unavailable"]))
        priorities=st.multiselect("Priority topics",list(lookup),default=settings["priorities"],format_func=lambda value:lookup[value]["name"])
        threshold=st.number_input("Strong-answer threshold (0–4)",min_value=1,max_value=4,value=settings["threshold"])
        successes=st.number_input("Required independent successful questions",min_value=2,max_value=5,value=settings["successes"])
        intervals=st.text_input("Review intervals in days",", ".join(map(str,settings["intervals"])))
        if st.form_submit_button("Save learning settings"):
            def save(_):
                try: ZoneInfo(zone)
                except ZoneInfoNotFoundError: raise ValueError("Choose an IANA timezone such as Asia/Kolkata.")
                dates=[line.strip() for line in unavailable.splitlines() if line.strip()]
                for date in dates+([interview] if interview else []): datetime.strptime(date,"%Y-%m-%d")
                sequence=[int(n.strip()) for n in intervals.split(",")]
                if not sequence or sequence!=sorted(sequence) or min(sequence)<1 or max(sequence)>365:
                    raise ValueError("Use increasing review intervals from 1 to 365 days.")
                learning.preference("settings",dict(timezone=zone,interview=interview,daily_minutes=daily,
                                                   session_minutes=length,unavailable=dates,priorities=priorities,
                                                   threshold=threshold,successes=successes,intervals=sequence))
                return True
            if app.action(save): st.rerun()
    if st.button("Propose revised seven-day plan"):
        proposal=app.action(lambda _:learning.propose(now))
        if proposal: st.session_state["proposal:"+app.record.id]=proposal
    proposal=st.session_state.get("proposal:"+app.record.id)
    if proposal:
        with st.expander("Proposed changes",expanded=True):
            st.write(proposal["reason"])
            current=learning.active_plan()
            st.write(f"Active activities · {len(current.get('blocks',[]))}. Proposed activities · {len(proposal['blocks'])}.")
            st.caption("Completed and pinned activities are preserved. Blocks are flexible daytime tasks; reserve five-minute breaks between blocks.")
            for block in proposal["blocks"]:
                st.write(f"{block['date']} · {block['name']} · {block['duration']} min · {block['outcome']}")
            if st.button("Apply proposed plan"):
                if app.action(lambda _:learning.apply_plan(proposal) or True):
                    del st.session_state["proposal:"+app.record.id]
                    st.rerun()
    for block in learning.active_plan().get("blocks",[]):
        with st.expander(f"{block['date']} · {block['name']} · {block['duration']} min"):
            st.write(block["activity"])
            st.caption(block["reason"])
            complete=st.checkbox("Completed",value=block["completed"],key="complete:"+block["id"])
            pinned=st.checkbox("Pinned activity",value=block["pinned"],key="activity-pin:"+block["id"])
            if st.button("Save activity",key="activity-save:"+block["id"]):
                learning.update_block(block["id"],"completed",complete)
                learning.update_block(block["id"],"pinned",pinned)
                st.rerun()


def diagnostic(learning,app):
    st.caption("Diagnostics reuse saved, current lesson questions. Generate lessons first if none are available. Each response uses the existing interview feedback flow.")
    lookup={t["id"]:t for t in learning.topics()}
    selected=st.selectbox("Diagnostic topic",list(lookup),format_func=lambda i:lookup[i]["name"])
    count=st.number_input("Diagnostic question count",min_value=1,max_value=5,value=3)
    relevant={selected,*lookup[selected]["prerequisites"]}
    names={lookup[i]["name"] for i in relevant}
    requests={r.slot:r for r in lesson_requests(app.profile)}
    questions=[]
    for item in app.store.items(app.record.id):
        if item.kind=="skill" and item.title.split(" · ")[0] in names and item.slot in requests and app.material.current(app.record,requests[item.slot],item):
            questions.extend((q,item.title.split(" · ")[0],item.title.split(" · ")[-1]) for q in parse_item(item).questions[:2])
    unique={q.question:(q,topic,level) for q,topic,level in questions}
    if st.button("Start diagnostic",disabled=not unique):
        turns=[Turn(question=PlannedQuestion(**q.model_dump()),topic=topic,difficulty=level) for q,topic,level in list(unique.values())[:count]]
        session=Session(profile_id=app.record.id,mode="Diagnostic",topic=lookup[selected]["name"],
                        difficulty="Basics",budget=len(turns),coach=True,turns=turns)
        Interviews(app.store).create(session)
        st.session_state["interview_target"]=session.id
        st.session_state["navigation_target"]="Interview Room"
        st.rerun()
    if not unique: st.info("Save a Basics lesson for this topic or a prerequisite to enable the diagnostic.")


def compare(learning):
    evidence=learning.evidence()
    if len(evidence)<2:
        st.info("At least two saved evaluations are needed for comparison.")
        return
    lookup={e["id"]:e for e in evidence}
    label=lambda ident:lookup[ident]["question"]+" · "+(lookup[ident]["time"] or "unknown date")+" · "+ident[-6:]
    first=st.selectbox("Earlier attempt",list(lookup),format_func=label)
    second=st.selectbox("Later attempt",list(lookup),index=1,format_func=label)
    a,b=lookup[first],lookup[second]
    if a["rubric"]=="unknown" or (a["rubric"],a["difficulty"])!=(b["rubric"],b["difficulty"]):
        st.warning("Rubric or difficulty metadata is incompatible or unknown. Scores are shown separately.")
    else:
        st.caption("Score differences are descriptive. Different questions, assistance or retries limit conclusions about improvement.")
        for dimension in a["scores"]:
            st.write(f"{dimension.title()} · {a['scores'][dimension]} → {b['scores'][dimension]} · change {b['scores'][dimension]-a['scores'][dimension]:+d}")
    st.write("Earlier gaps",a["missing"])
    st.write("Later gaps",b["missing"])
    st.caption("Sample size · one answer per selection")
