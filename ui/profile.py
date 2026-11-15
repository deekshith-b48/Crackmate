"""Resume review, explicit profile creation and editable profile fields."""
import hashlib

import streamlit as st

from core.resume import read_upload, reviewed_text
from core.schemas import Profile, ProfileDraft, Project, Skills


SKILL_LABELS = {
    "language": "Programming languages", "frontend": "Frontend", "backend": "Backend",
    "database": "Databases", "cloud_devops": "Cloud and DevOps", "tools": "Tools", "other": "Other skills",
}


def lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def tags(text):
    return list(dict.fromkeys(tag.strip() for tag in text.split(",") if tag.strip()))


def target_fields(profile=None):
    role = st.text_input("Target role (optional)", value=profile.role or "" if profile else "", max_chars=200)
    company = st.text_input("Company (optional)", value=profile.company or "" if profile else "", max_chars=200)
    description = st.text_area("Job description (optional)", value=profile.job_description or "" if profile else "",
                               max_chars=8000, height=112)
    return {"role": role.strip() or None, "company": company.strip() or None, "job_description": description.strip() or None}


def create(app, profile):
    record = app.store.create(profile)
    st.session_state["profile_target"] = record.id
    st.session_state["resume_reset"] = True
    st.session_state["notice"] = "Profile saved. Review and correct the details before generating lessons."
    st.rerun()


def resume_input(app):
    st.subheader("Review your resume")
    mode = st.radio("Resume source", ["Paste text", "Upload PDF or LaTeX"], horizontal=True)
    limits = app.settings.limits
    if mode != "Paste text":
        upload = st.file_uploader("Resume file", type=["pdf", "tex"], max_upload_size=limits.file_bytes // 1024**2,
                                  key=f"_upload_{st.session_state.get('upload_generation', 0)}")
        if upload:
            data = upload.getvalue()
            signature = (upload.name, hashlib.sha256(data).hexdigest())
            if st.session_state.get("upload_signature") != signature:
                if st.button("Read file into preview"):
                    result = app.action(lambda _: read_upload(upload.name, data, limits))
                    if result is not None:
                        st.session_state["resume_text"] = result
                        st.session_state["_resume_text"] = result
                        st.session_state["upload_signature"] = signature
            else:
                st.caption("File loaded into the editable preview.")
    if "_resume_text" not in st.session_state:
        st.session_state["_resume_text"] = st.session_state.get("resume_text", "")
    preview = st.text_area(
        "Editable resume preview", height=240, key="_resume_text",
        placeholder="Paste resume text here or read an uploaded PDF or LaTeX file.",
    )
    st.session_state["resume_text"] = preview
    st.caption(f"Up to {limits.text_chars:,} characters. Remove contact details and anything you want to keep private.")
    with st.form("extract"):
        target = target_fields()
        st.caption("Extract profile sends the reviewed resume text to Groq. Target details stay local until used for generation.")
        consent = st.checkbox("Send the reviewed resume text to Groq")
        submit = st.form_submit_button("Extract profile", type="primary", disabled=not app.settings.api_key)
        if submit:
            if not consent:
                st.error("Confirm that you want to send the reviewed text.")
                return
            def extract(progress):
                text = reviewed_text(preview, limits)
                result, _ = app.service.generate("profile", {"reviewed_resume": text}, ProfileDraft, progress=progress)
                return Profile.from_draft(result, **target)

            profile = app.action(extract, "Extracting and validating profile…")
            if profile is not None:
                app.action(lambda _: create(app, profile))


def profile_fields(app):
    record = app.record
    profile = record.profile
    st.subheader("Profile details")
    with st.form(f"profile:{record.id}:{record.revision}"):
        name = st.text_input("Name (optional)", profile.name or "", max_chars=200)
        summary = st.text_area("Summary", profile.summary or "", max_chars=8000)
        experience = st.text_input("Experience level", profile.experience_level or "", max_chars=200)
        work = st.text_area("Work experience (one entry per line)", "\n".join(profile.work_experience))
        education = st.text_area("Education (one entry per line)", "\n".join(profile.education))
        with st.expander("Skills by category", expanded=True):
            skills = {key: tags(st.text_input(label, ", ".join(getattr(profile.skills, key)), help="Separate skills with commas."))
                      for key, label in SKILL_LABELS.items()}
        with st.expander("Interview target"):
            target = target_fields(profile)
        if st.form_submit_button("Save profile details", type="primary"):
            updated = app.action(lambda _: Profile(
                name=name.strip() or None, summary=summary.strip() or None, experience_level=experience.strip() or None,
                skills=Skills(**skills), work_experience=lines(work), education=lines(education),
                projects=profile.projects, **target
            ))
            if updated is not None:
                app.save(updated)


def edit_projects(app):
    projects = app.profile.projects
    options = [project.id for project in projects] + ["new"]
    lookup = {project.id: project for project in projects}
    st.subheader("Project details")
    selected = st.selectbox("Project to edit", options, format_func=lambda value: lookup[value].title if value in lookup else "Add a project",
                            key=f"edit:{app.record.id}")
    project = lookup.get(selected)
    with st.form(f"edit-project:{app.record.id}:{app.record.revision}:{selected}"):
        title = st.text_input("Project title", project.title if project else "", max_chars=200)
        summary = st.text_area("Project summary", project.summary if project else "", max_chars=2400)
        technologies = st.text_input("Technologies (comma separated)", ", ".join(project.technologies) if project else "")
        contribution = st.text_area("Your contribution", project.contribution if project else "", max_chars=2400)
        implementation = st.text_area("Known implementation details", project.implementation if project else "", max_chars=3500)
        remove = project and st.checkbox("Remove this project from the profile")
        if st.form_submit_button("Save project"):
            def change(_):
                entries = [p for p in projects if not remove or p.id != selected]
                if not remove:
                    base = project.model_dump() if project else {}
                    base.update(title=title, summary=summary, technologies=tags(technologies),
                                contribution=contribution, implementation=implementation)
                    edited = Project.model_validate(base)
                    entries = [edited if p.id == selected else p for p in entries] if project else entries + [edited]
                return Profile.model_validate(app.profile.model_dump() | {"projects": entries})
            updated = app.action(change)
            if updated is not None:
                app.save(updated)


def render(app):
    st.title("Resume and profile")
    st.caption("Review what CrackMate knows about your experience before using it to generate study material.")
    if app.record:
        profile_fields(app)
        edit_projects(app)
        with st.expander("Create another profile"):
            resume_input(app)
            if st.button("Start with a blank profile"):
                app.action(lambda _: create(app, Profile()))
        with st.expander("Delete this preparation profile"):
            st.write("Deletes this profile and all its local lessons, practice attempts, progress and cache entries.")
            st.caption("Previously downloaded exports and data sent to Groq are outside local deletion.")
            confirm = st.checkbox("Permanently delete this profile and its local data", key=f"confirm:{app.record.id}")
            if st.button("Delete profile", disabled=not confirm):
                def delete(_):
                    app.store.delete(app.record.id)
                    for key in list(st.session_state):
                        del st.session_state[key]
                    st.session_state["notice"] = "Preparation profile deleted."
                    st.rerun()
                app.action(delete)
    else:
        resume_input(app)
        st.divider()
        if st.button("Start with a blank profile"):
            app.action(lambda _: create(app, Profile()))
