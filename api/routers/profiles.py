"""Profile, resume and project endpoints."""
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from api.deps import Core, core
from api.services import profiles as svc
from api.streaming import stream_job
from core.resume import read_upload

router = APIRouter(prefix="/api")


class Target(BaseModel):
    role: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    job_description: str | None = Field(default=None, max_length=8000)


class ExtractIn(Target):
    text: str = Field(max_length=60_000)
    consent: bool = False


class DetailsIn(Target):
    revision: int
    name: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=8000)
    experience_level: str | None = Field(default=None, max_length=200)
    skills: dict[str, list[str]] = {}
    work_experience: list[str] = []
    education: list[str] = []


class ProjectIn(BaseModel):
    revision: int
    title: str = Field(max_length=200)
    summary: str = Field(default="", max_length=2400)
    technologies: list[str] = []
    contribution: str = Field(default="", max_length=2400)
    implementation: str = Field(default="", max_length=3500)


class ClarifyIn(BaseModel):
    revision: int
    answers: dict[str, str] = {}
    reference: str = Field(default="", max_length=3500)


@router.get("/profile-form")
def form_labels():
    return {"skill_labels": svc.SKILL_LABELS, "clarifications": svc.CLARIFICATIONS}


@router.post("/resume/read")
def read_resume(file: UploadFile = File(...), c: Core = Depends(core)):
    limits = c.settings.limits
    data = file.file.read(limits.file_bytes + 1)  # never load more than the limit
    return {"text": read_upload(file.filename or "", data, limits)}


@router.post("/profiles")
def create_blank(c: Core = Depends(core)):
    return svc.create_blank(c)


@router.post("/profile/extract")
def extract(body: ExtractIn, c: Core = Depends(core)):
    target = body.model_dump(include={"role", "company", "job_description"})
    return stream_job(lambda progress: svc.create_from_resume(c, body.text, target, body.consent, progress))


@router.get("/profiles/{pid}")
def get_profile(pid: str, c: Core = Depends(core)):
    return svc.view(svc.get_record(c, pid))


@router.put("/profiles/{pid}")
def update_profile(pid: str, body: DetailsIn, c: Core = Depends(core)):
    return svc.update_details(c, pid, body.revision, body)


@router.delete("/profiles/{pid}")
def delete_profile(pid: str, confirm: bool = False, c: Core = Depends(core)):
    svc.delete_profile(c, pid, confirm)
    return {"deleted": True}


@router.post("/profiles/{pid}/projects")
def add_project(pid: str, body: ProjectIn, c: Core = Depends(core)):
    return svc.add_project(c, pid, body.revision, body)


@router.put("/profiles/{pid}/projects/{project_id}")
def update_project(pid: str, project_id: str, body: ProjectIn, c: Core = Depends(core)):
    return svc.update_project(c, pid, body.revision, project_id, body)


@router.delete("/profiles/{pid}/projects/{project_id}")
def remove_project(pid: str, project_id: str, revision: int, c: Core = Depends(core)):
    return svc.remove_project(c, pid, revision, project_id)


@router.put("/profiles/{pid}/projects/{project_id}/clarification")
def clarify(pid: str, project_id: str, body: ClarifyIn, c: Core = Depends(core)):
    return svc.save_clarification(c, pid, body.revision, project_id, body.answers, body.reference)
