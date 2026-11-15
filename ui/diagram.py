"""Likely project architecture as a Mermaid diagram, with assumptions labelled."""
import html

import streamlit as st
import streamlit.components.v1 as components

from core.export import diagram_markdown
from core.material import diagram_request
from core.schemas import Diagram
from ui.common import download, safe_markdown
from ui.lessons import select

MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.0/dist/mermaid.esm.min.mjs"


def diagram_html(source):
    # Escaped text plus strict security level: model output can't inject markup or click handlers.
    return (f'<pre class="mermaid">{html.escape(source, quote=False)}</pre>'
            f'<script type="module">import mermaid from "{MERMAID}";'
            'mermaid.initialize({startOnLoad:true,securityLevel:"strict"});</script>')


def render(app):
    st.title("Architecture")
    st.caption("A likely architecture for each project. Dashed nodes are assumptions, not facts from your resume.")
    lookup = {p.id: p for p in app.profile.projects}
    if not lookup:
        st.info("Add a project in Resume and profile to begin.")
        return
    project = lookup[select(app, "Project", list(lookup), format_func=lambda v: lookup[v].title)]
    request, record = diagram_request(app.profile, project), app.record
    item = app.store.item(record.id, request.slot)
    current = item is not None and app.material.current(record, request, item)
    start, redo = st.columns(2)
    go = start.button("Load saved diagram" if current else "Draw architecture", type="primary",
                      disabled=not current and not app.settings.api_key)
    again = bool(item) and redo.button("Redraw", disabled=not app.settings.api_key)
    if go or again:
        result = app.action(lambda progress: app.material.generate(
            record, request, regenerate=again, progress=progress), "Drawing and checking the diagram…")
        if result:
            item, current = result[0], True
    if not item:
        st.info("Your diagram is ready to draw when you need it.")
        return
    if not current:
        st.warning("Outdated · The project changed since this diagram was drawn.")
    result = Diagram.model_validate_json(item.body)
    components.html(diagram_html(result.diagram), height=520, scrolling=True)
    st.caption("Rendering needs internet access to load Mermaid. If the picture is blank, copy the source below into mermaid.live.")
    with st.expander("Mermaid source"):
        st.code(result.diagram, language="text")
    with st.expander("Assumptions to confirm", expanded=True):
        safe_markdown(result.assumptions)
    download("Download diagram", diagram_markdown(item.title, result), "crackmate-architecture.md", f"diagram:{project.id}")
