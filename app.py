"""Run with python -m streamlit run app.py."""
import sqlite3

import streamlit as st

from core.config import Settings
from core.export import NOTICE, all_markdown
from core.llm import ModelService
from core.review import Reviews
from core.material import Material, lesson_requests
from core.storage import Storage
from ui import company, diagram, review, claims, lessons, pitch, plan, practice, profile, knowledge, interview, learning
from ui.common import App, download


PAGES = {
    "Resume and profile": profile.render,
    "Projects": lessons.projects,
    "Skills": lessons.skills,
    "Claim Checker": claims.render,
    "Project Pitch": pitch.render,
    "Architecture": diagram.render,
    "Review today": review.render,
    "Practice": practice.render,
    "Preparation plan": plan.render,
    "Knowledge Library": knowledge.render,
    "Company DSA": company.render,
    "Interview Room": interview.render,
    "Learning Progress": learning.render,
}


def main():
    st.set_page_config(page_title="CrackMate", layout="centered", initial_sidebar_state="expanded")
    if st.session_state.pop("resume_reset", False):
        for key in ("resume_text", "_resume_text", "upload_signature"):
            st.session_state.pop(key, None)
        st.session_state["upload_generation"] = st.session_state.get("upload_generation", 0) + 1
    try:
        try:
            settings = Settings.load(st.secrets)
        except FileNotFoundError:
            settings = Settings.load({})
    except (ValueError, TypeError):
        st.error("Configuration needs attention. Check your environment and Streamlit secrets against the README.")
        return
    try:
        store = Storage(settings.database)
        profiles = {record.id: record for record in store.profiles()}
    except (OSError, sqlite3.Error):
        st.error("CrackMate could not open its local database. Check that .crackmate is writable.")
        return
    service = ModelService(settings)
    material = Material(store, service)
    with st.sidebar:
        st.markdown("## CrackMate")
        st.caption("Interview preparation")
        if target := st.session_state.pop("profile_target", None):
            st.session_state["active_profile"] = target
        if st.session_state.get("active_profile") not in profiles:
            st.session_state["active_profile"] = next(iter(profiles), None)
        if profiles:
            selected = st.selectbox(
                "Preparation profile", list(profiles), key="active_profile",
                format_func=lambda ident: f"{profiles[ident].profile.name or profiles[ident].profile.role or 'Profile'} · {ident[:6]}",
            )
            record = profiles[selected]
        else:
            st.caption("No saved profiles")
            record = None
        if target := st.session_state.pop("navigation_target", None):
            st.session_state["navigation"] = target
        page = st.radio("Go to", list(PAGES), key="navigation")
        st.divider()
        if record:
            items = store.items(record.id)
            attempts = store.attempts(record.id)
            requests = {request.slot: request for request in lesson_requests(record.profile)}
            study_items = [item for item in items if item.kind in ("project", "skill")]
            def is_current(item):
                if item.kind == "plan":
                    return plan.plan_status(app, item, study_items, attempts)
                return item.slot in requests and material.current(record, requests[item.slot], item)
            app = App(settings, store, service, material, record)
            done = sum(store.completed(record.id, item) for item in study_items if is_current(item))
            st.caption(f"{done} completed lessons · {len(attempts)} practice attempts")
            if due := len(Reviews(store).due(record.id)):
                st.caption(f"{due} questions due in Review today")
            if items:
                download("Download all material", all_markdown(record.profile, items, is_current),
                         "crackmate-preparation.md", "all-download")
        with st.expander("Privacy and model"):
            st.caption("Profiles and generated material are stored on this computer. Generating sends the relevant context to Groq.")
            st.caption(f"Configured model · {settings.model}")
            st.caption(NOTICE)

    if notice := st.session_state.pop("notice", None):
        st.success(notice)
    if not settings.api_key:
        st.info("Groq setup needed for generation. Set GROQ_API_KEY as shown in the README, then restart. You can still edit profiles and read saved lessons.")
    app = App(settings, store, service, material, record)
    if page not in ("Resume and profile", "Knowledge Library", "Company DSA") and record is None:
        st.title(page)
        st.info("Create a preparation profile in Resume and profile to begin.")
    else:
        PAGES[page](app)


if __name__ == "__main__":
    main()
