"""Project clarification and selective lesson generation."""
import streamlit as st

from core.export import project_markdown
from core.material import LEVELS, SECTIONS, generate_many, project_request, skill_request, topics
from core.schemas import Profile, Project
from ui.common import download, generator


CLARIFICATIONS = {
    "problem": "What problem does the project solve?",
    "contribution": "What did you personally implement?",
    "request_flow": "How does a user request travel through the system?",
    "database_deployment": "Which database and deployment environment are used, if any?",
    "access": "How are authentication and authorisation handled, if applicable?",
    "challenge": "What was the hardest problem?",
    "improvements": "What limitations or improvements are known?",
}


def clarify(app, project):
    with st.expander("Clarify the project (optional)"):
        st.caption("Add details you can confirm or skip unknown answers. Remove credentials and private information from snippets.")
        with st.form(f"clarification:{app.record.id}:{app.record.revision}:{project.id}"):
            answers = {
                key: st.text_area(label, project.clarification.get(key, ""), max_chars=500, height=80)
                for key, label in CLARIFICATIONS.items()
            }
            reference = st.text_area("README or selected code (optional)", project.reference, max_chars=3500)
            st.caption("Saved details and excerpts are included in project generation requests to Groq.")
            if st.form_submit_button("Save clarification"):
                def update(_):
                    edited = Project.model_validate(project.model_dump() | {
                        "clarification": {key: value.strip() for key, value in answers.items() if value.strip()},
                        "reference": reference,
                    })
                    return Profile.model_validate(app.profile.model_dump() | {
                        "projects": [edited if p.id == project.id else p for p in app.profile.projects]
                    })
                profile = app.action(update)
                if profile is not None:
                    app.save(profile)


def select(app, key, options, default=None, format_func=str):
    # Durable selection lets a study-plan link open the exact project section or lesson.
    widget = f"{key}:{app.record.id}"
    value = st.session_state.get(key)
    if value not in options:
        value = default if default in options else next(iter(options))
    selected = st.selectbox(key, options, index=list(options).index(value), key=widget, format_func=format_func)
    st.session_state[key] = selected
    return selected


def projects(app):
    st.title("Projects")
    st.caption("Learn the concepts behind your project and practise explaining your decisions.")
    lookup = {project.id: project for project in app.profile.projects}
    if not lookup:
        st.info("Add a project in Resume and profile to begin.")
        return
    selected = select(app, "Project", list(lookup), format_func=lambda value: lookup[value].title)
    project = lookup[selected]
    section = select(app, "Project section", list(SECTIONS))
    st.caption(SECTIONS[section])
    requests = {request.slot: request for request in (project_request(app.profile, project, name) for name in SECTIONS)}
    items = [item for item in app.store.items(app.record.id) if item.slot in requests]
    clarify(app, project)
    st.caption(f"{sum(app.material.current(app.record, requests[item.slot], item) for item in items)} of {len(SECTIONS)} sections saved and current")
    if st.button("Generate all missing sections", disabled=not app.settings.api_key,
                 help="Runs up to three sections at the same time."):
        result = app.action(lambda progress: generate_many(
            app.material, app.record, list(requests.values()), progress=progress), "Generating sections…")
        if result:
            done, failed = result
            st.session_state["notice"] = f"{done} sections generated." + (
                f" Could not finish: {', '.join(failed)}. Try those again." if failed else "")
            st.rerun()
    generator(app, project_request(app.profile, project, section))
    if app.store.item(app.record.id, f"project:{project.id}:{section}") or items:
        items = [item for item in app.store.items(app.record.id) if item.slot in requests]
        download("Download project deep-dive", project_markdown(
            project, items, lambda item: app.material.current(app.record, requests[item.slot], item)
        ), "crackmate-project.md", f"project-export:{project.id}")


def skills(app):
    st.title("Skills")
    st.caption("Work through one concept at a time, from prerequisites to practice.")
    from core.learning import Learning
    available = list(dict.fromkeys(topics(app.profile) + [t["name"] for t in Learning(app.store, app.record.id).topics()]))
    topic = select(app, "Topic", available)
    level = select(app, "Difficulty", list(LEVELS))
    st.caption(f"{app.material.cache.count()} shared lessons ready to load instantly. Build more with "
               "`python -m core.pregen`.")
    generator(app, skill_request(app.profile, topic, level), tailor_button=True)
