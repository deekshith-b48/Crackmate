"""Question card: think first, reveal, then rate. Rating schedules the next review."""
import streamlit as st

from core.material import ladder_request
from core.review import GRADES, Reviews, question_id
from core.schemas import Ladder
from ui.common import safe_markdown

LEVELS = (("Easy", "green"), ("Medium", "orange"), ("Hard", "red"))


def question_card(app, slot, question, answer, hint, position=0, total=1, group=""):
    uid = question_id(slot, f"{group}:{position}:{question}")  # unique per card even if text repeats
    shown = f"reveal:{uid}"
    with st.container(border=True):
        if total > 1:  # difficulty comes from the order within the lesson, not from a model rating
            label, colour = LEVELS[position * 3 // total]
            st.badge(label, color=colour)
        st.markdown(f"**{question}**")
        if hint:
            st.caption(f"Hint: {hint}")
        if not st.session_state.get(shown) and st.button("Show answer", key=f"show:{uid}"):
            st.session_state[shown] = True
        if st.session_state.get(shown):
            safe_markdown(answer)
            ladder(app, slot, question, answer, uid)
            st.caption("How well did you recall it?")
            for column, grade in zip(st.columns(len(GRADES)), GRADES):
                if column.button(grade, key=f"grade:{grade}:{uid}"):
                    days = Reviews(app.store).rate(app.record.id, slot, question, answer, hint, grade)
                    st.session_state.pop(shown, None)
                    st.session_state["notice"] = "Due again today." if days == 0 else f"Next review in {days} day(s)."
                    st.rerun()


def ladder(app, slot, question, answer, uid):
    request, record = ladder_request(app.profile, slot, question_id(slot, question), question, answer), app.record
    item = app.store.item(record.id, request.slot)
    current = item is not None and app.material.current(record, request, item)
    if not current:
        if st.button("Build follow-up ladder", key=f"ladder:{uid}", disabled=not app.settings.api_key):
            result = app.action(lambda progress: app.material.generate(
                record, request, regenerate=bool(item), progress=progress), "Building follow-ups…")
            if result:
                item, current = result[0], True
    if current:
        st.markdown("**Follow-up ladder** · most likely, never guaranteed")
        for number, step in enumerate(Ladder.model_validate_json(item.body).steps, 1):
            with st.expander(f"{number} · {step.level.replace('_', ' ').capitalize()}: {step.question}"):
                safe_markdown(step.answer)
