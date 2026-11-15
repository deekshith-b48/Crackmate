"""A short question-by-question session and saved feedback history."""
from uuid import uuid4

import streamlit as st

from core.export import parse_item
from core.material import lesson_requests
from core.practice import RUBRIC, SCALE, review_answer
from ui.common import safe_markdown


def feedback_display(feedback, behavioural=False):
    from core.export import evidence_markdown
    safe_markdown(evidence_markdown(feedback))
    st.caption(f"Coaching estimates on a 0–4 scale. {SCALE}")
    labels = dict(zip(RUBRIC, ("Relevance", "Specificity", "Structure", "Reflection"))) if behavioural else RUBRIC
    for key, label in labels.items():
        score = getattr(feedback, key)
        st.markdown(f"**{label} · {score.score}/4**")
        safe_markdown(score.reason)
    for title, value in (
        ("What was correct", feedback.correct),
        ("What to work on", feedback.missing),
        ("Corrected explanation", feedback.corrected),
        ("Follow-up question", feedback.follow_up),
    ):
        st.markdown(f"**{title}**")
        safe_markdown(value)


def render(app):
    record = app.record
    st.title("Practice")
    st.caption("Answer one question at a time, then review the feedback before moving on.")
    requests = {request.slot: request for request in lesson_requests(app.profile)}
    items = {
        item.slot: item for item in app.store.items(record.id)
        if item.slot in requests and app.material.current(record, requests[item.slot], item)
    }
    if not items:
        st.info("Generate a current project or skill lesson to unlock its practice questions.")
    else:
        session(app, requests, items)

    st.subheader("Attempt history")
    attempts = app.store.attempts(record.id)
    if not attempts:
        st.caption("Submitted answers and feedback will appear here.")
    else:
        attempt_id = st.selectbox(
            "Saved attempt", [a.id for a in attempts],
            format_func=lambda ident: next(f"{a.created_at} UTC · {a.focus} · {a.question}" for a in attempts if a.id == ident),
            key=f"history:{record.id}",
        )
        attempt = next(a for a in attempts if a.id == attempt_id)
        with st.expander("Review saved answer and feedback"):
            st.text(attempt.question)
            st.text(attempt.answer)
            feedback_display(attempt.feedback)


def session(app, requests, items):
    record = app.record
    slot = st.selectbox("Practice focus", list(items), format_func=lambda value: items[value].title,
                        key=f"focus:{record.id}")
    item = items[slot]
    questions = parse_item(item).questions[:3]
    state_key = f"practice:{record.id}"
    session_key = (slot, item.digest, item.body)
    state = st.session_state.get(state_key)
    if not state or state["lesson"] != session_key:
        state = {"lesson": session_key, "index": 0, "attempt": uuid4().hex}
        st.session_state[state_key] = state

    def advance(index):
        st.session_state[state_key] = {"lesson": session_key, "index": index, "attempt": uuid4().hex}
        st.rerun()

    index, attempt_id = state["index"], state["attempt"]
    if index >= len(questions):
        st.success("Practice session complete. Revisit your attempts below.")
        if st.button("Start again"):
            advance(0)
        return

    question = questions[index]
    st.progress(index / len(questions), text=f"Question {index + 1} of {len(questions)}")
    st.subheader(question.question)
    if st.button("Show hint", key=f"hint:{attempt_id}"):
        state["hint"] = True
    if state.get("hint"):
        safe_markdown(question.hint)
    if st.button("Reveal example answer", key=f"reveal:{attempt_id}"):
        state["revealed"] = True
    if state.get("revealed"):
        safe_markdown(question.answer)
    feedback = next((a.feedback for a in app.store.attempts(record.id) if a.id == attempt_id), None)
    if feedback is None:
        with st.form(f"answer:{attempt_id}"):
            answer = st.text_area("Your answer", max_chars=3500, height=160)
            if st.form_submit_button("Get feedback", type="primary", disabled=not app.settings.api_key):
                feedback = app.action(lambda progress: review_answer(
                    app.store, app.service, record, attempt_id, requests[slot], question, answer, progress,
                    assistance={"hint":state.get("hint",False),"revealed":state.get("revealed",False)},
                ), "Reviewing your answer…")
    if feedback:
        st.subheader("Feedback")
        feedback_display(feedback)
    if st.button("Next question" if feedback else "Skip question", key=f"next:{attempt_id}"):
        advance(index + 1)
