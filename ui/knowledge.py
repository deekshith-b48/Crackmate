import hashlib
import streamlit as st
from core.knowledge import Library
from core.fetch import fetch, extract
from core.ingest import build


def render(app):
    st.title("Knowledge Library")
    st.caption("Shared personal library. Deleting a preparation profile leaves these sources available.")
    library=Library(app.store)
    st.info("Import selected public URLs, files or pasted text, or build the study knowledge base below.")
    with st.expander("Build the study knowledge base (about 70 MB download, one time)"):
        st.caption("Downloads System Design Primer (CC BY 4.0), Tech Interview Handbook (MIT) and Coding Interview "
                   "University (CC BY-SA 4.0), keeps only their text with links back to the originals, then deletes the "
                   "downloads. Saved lessons may show as outdated afterwards because they gain better sources.")
        if st.button("Build knowledge base"):
            def run_build(progress):
                totals, failed = build(library, app.settings.database.parent, log=progress)
                if failed:
                    raise ValueError("Could not download: " + ", ".join(failed) + ". Check git and your connection.")
                return f"Imported {totals['Imported']} sections, {totals['Unchanged']} unchanged."
            result = app.action(run_build, "Building knowledge base…")
            if result:
                st.success(result)
    with st.form("source-import"):
        title=st.text_input("Source title",max_chars=200)
        url=st.text_input("Public source URL (optional)")
        upload=st.file_uploader("Source file",type=["txt","md","pdf"],max_upload_size=2)
        pasted=st.text_area("Source text",max_chars=100000)
        license=st.text_input("Reuse terms or license (leave Unknown when uncertain)",value="Unknown")
        if st.form_submit_button("Import source"):
            def run(_):
                location=url.strip()
                body=pasted
                kind="pasted"
                if upload:
                    body=extract(upload.name,upload.getvalue())
                    location="file:"+upload.name
                    kind="file"
                elif not pasted and location:
                    location,mime,data=fetch(location)
                    body=extract(location,data,mime)
                    kind="web"
                location=location or "pasted:"+hashlib.sha256(body.encode()).hexdigest()
                return library.import_text(title or location,location,body,kind,license)
            result=app.action(run,"Importing source…")
            if result: st.success(result)
    sources=library.sources()
    st.caption(f"{len(sources)} sources. Publication dates and publisher identities are unknown unless independently verified.")
    query=st.text_input("Search saved passages")
    if query:
        for passage in library.search(query):
            with st.expander(passage["title"]+" · "+passage["heading"]):
                st.text(passage["text"])
                st.text(passage["location"])
    if sources:
        source_id=st.selectbox("Saved source",[s["id"] for s in sources],
                               format_func=lambda ident:next(s["title"] for s in sources if s["id"]==ident))
        source=next(s for s in sources if s["id"]==source_id)
        st.json(source)
        if source["kind"]=="web" and st.button("Refresh source"):
            def refresh(_):
                try:
                    location,mime,data=fetch(source["location"])
                    return library.import_text(source["title"],source["location"],extract(location,data,mime),"web",source["license"])
                except ValueError as exc:
                    library.failed(source_id,str(exc))
                    raise
            app.action(refresh,"Refreshing…")
        confirm=st.checkbox("Delete source and its indexed passages")
        if st.button("Delete source",disabled=not confirm):
            library.delete(source_id)
            st.rerun()
