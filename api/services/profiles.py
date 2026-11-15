"""Profile logic moved out of ui/profile.py and ui/lessons.py so the API stays thin and testable."""
from api.errors import NotFound
from core.resume import reviewed_text
from core.schemas import Profile, ProfileDraft, Project, Skills
from core.storage import StorageError

SKILL_LABELS = {
    "language": "Programming languages", "frontend": "Frontend", "backend": "Backend",
    "database": "Databases", "cloud_devops": "Cloud and DevOps", "tools": "Tools", "other": "Other skills",
}
CLARIFICATIONS = {
    "problem": "What problem does the project solve?",
    "contribution": "What did you personally implement?",
    "request_flow": "How does a user request travel through the system?",
    "database_deployment": "Which database and deployment environment are used, if any?",
    "access": "How are authentication and authorisation handled, if applicable?",
    "challenge": "What was the hardest problem?",
    "improvements": "What limitations or improvements are known?",
}


def lines(values):
    return [line.strip() for line in values if line and line.strip()]


def tags(values):
    return list(dict.fromkeys(tag.strip() for tag in values if tag and tag.strip()))


def blank(value):
    return (value or "").strip() or None


def get_record(core, pid):
    record = core.store.get(pid)
    if record is None:
        raise NotFound("This profile no longer exists.")
    return record


def view(record):
    return {"id": record.id, "revision": record.revision, "profile": record.profile.model_dump(mode="json")}


def create_blank(core):
    return view(core.store.create(Profile()))


def create_from_resume(core, text, target, consent, progress):
    """Extract a profile from reviewed resume text. Sends the text to Groq only after consent."""
    if not consent:
        raise ValueError("Confirm that you want to send the reviewed text.")
    reviewed = reviewed_text(text, core.settings.limits)
    draft, _ = core.service.generate("profile", {"reviewed_resume": reviewed}, ProfileDraft, progress=progress)
    profile = Profile.from_draft(draft, role=blank(target.get("role")), company=blank(target.get("company")),
                                 job_description=blank(target.get("job_description")))
    return view(core.store.create(profile))


def _fresh(core, pid, revision):
    record = get_record(core, pid)
    if revision != record.revision:
        raise StorageError("This profile changed in another tab. Reload it and apply your edits again.")
    return record


def update_details(core, pid, revision, data):
    record = _fresh(core, pid, revision)
    profile = Profile(
        name=blank(data.name), summary=blank(data.summary), experience_level=blank(data.experience_level),
        skills=Skills(**{key: tags(data.skills.get(key, [])) for key in SKILL_LABELS}),
        work_experience=lines(data.work_experience), education=lines(data.education),
        projects=record.profile.projects, role=blank(data.role), company=blank(data.company),
        job_description=blank(data.job_description),
    )
    return view(core.store.save(record, profile))


def _with_projects(record, projects):
    return Profile.model_validate(record.profile.model_dump() | {"projects": projects})


def _project_fields(data):
    return {"title": data.title, "summary": data.summary, "technologies": tags(data.technologies),
            "contribution": data.contribution, "implementation": data.implementation}


def add_project(core, pid, revision, data):
    record = _fresh(core, pid, revision)
    project = Project.model_validate(_project_fields(data))
    return view(core.store.save(record, _with_projects(record, record.profile.projects + [project])))


def update_project(core, pid, revision, project_id, data):
    record = _fresh(core, pid, revision)
    projects = record.profile.projects
    if not any(p.id == project_id for p in projects):
        raise NotFound("This project no longer exists.")
    edited = [Project.model_validate(p.model_dump() | _project_fields(data)) if p.id == project_id else p for p in projects]
    return view(core.store.save(record, _with_projects(record, edited)))


def remove_project(core, pid, revision, project_id):
    record = _fresh(core, pid, revision)
    return view(core.store.save(record, _with_projects(record, [p for p in record.profile.projects if p.id != project_id])))


def save_clarification(core, pid, revision, project_id, answers, reference):
    record = _fresh(core, pid, revision)
    clean = {key: value.strip() for key, value in answers.items() if key in CLARIFICATIONS and value.strip()}
    if any(len(value) > 500 for value in clean.values()):
        raise ValueError("Each answer can be up to 500 characters.")
    if not any(p.id == project_id for p in record.profile.projects):
        raise NotFound("This project no longer exists.")
    edited = [Project.model_validate(p.model_dump() | {"clarification": clean, "reference": reference})
              if p.id == project_id else p for p in record.profile.projects]
    return view(core.store.save(record, _with_projects(record, edited)))


def delete_profile(core, pid, confirm):
    get_record(core, pid)
    if not confirm:
        raise ValueError("Confirm that you want to permanently delete this profile and its local data.")
    core.store.delete(pid)
