"""2-minute spoken project pitch to rehearse."""
import streamlit as st

from core.export import pitch_markdown
from core.material import pitch_request
from core.schemas import Pitch
from ui.common import download, safe_markdown
from ui.lessons import select


def render(app):
    st.title("Project Pitch")
    st.caption("A spoken-style 2-minute pitch. Read it aloud, then rehearse it in your own words.")
    lookup = {p.id: p for p in app.profile.projects}
    if not lookup:
        st.info("Add a project in Resume and profile to begin.")
        return
    project = lookup[select(app, "Project", list(lookup), format_func=lambda v: lookup[v].title)]
    request, record = pitch_request(app.profile, project), app.record
    item = app.store.item(record.id, request.slot)
    current = item is not None and app.material.current(record, request, item)
    start, redo = st.columns(2)
    go = start.button("Load saved pitch" if current else "Write my pitch", type="primary",
                      disabled=not current and not app.settings.api_key)
    again = bool(item) and redo.button("Rewrite pitch", disabled=not app.settings.api_key)
    if go or again:
        result = app.action(lambda progress: app.material.generate(
            record, request, regenerate=again, progress=progress), "Writing and checking your pitch…")
        if result:
            item, current = result[0], True
    if not item:
        st.info("Your pitch is ready to write when you need it.")
        return
    if not current:
        st.warning("Outdated · The project or target changed since this pitch was written.")
    pitch = Pitch.model_validate_json(item.body)
    words = len(pitch.pitch.split())
    st.subheader(pitch.opening)
    safe_markdown(pitch.pitch)
    st.caption(f"About {words} words · roughly {max(1, round(words / 140))} minutes spoken")
    st.markdown("#### Be ready to expand on")
    safe_markdown("\n".join(f"- {point}" for point in pitch.key_points))
    with st.expander("Assumptions", expanded=True):
        safe_markdown(pitch.assumptions)
    download("Download pitch", pitch_markdown(item.title, pitch), "crackmate-pitch.md", f"pitch:{project.id}")
