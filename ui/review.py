"""Review today: questions due for spaced repetition."""
import streamlit as st

from core.review import Reviews
from ui.cards import question_card


def render(app):
    st.title("Review today")
    st.caption("Recall the answer first, then rate yourself. Rating decides when you see it again.")
    due = Reviews(app.store).due(app.record.id)
    if not due:
        st.info("Nothing is due. Open a lesson and rate its questions to start your review queue.")
        return
    st.metric("Questions due", len(due))
    row = due[0]
    question_card(app, row["slot"], row["question"], row["answer"], row["hint"])
