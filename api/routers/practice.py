"""Practice and Interview Room endpoints."""
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from api.deps import Core, core
from api.routers.learn import record
from api.services import interviews, practice
from api.streaming import stream_job

router = APIRouter(prefix="/api/profiles/{pid}")


class AnswerIn(BaseModel):
    slot: str
    index: int
    attempt_id: str = Field(min_length=8, max_length=64)
    text: str = Field(max_length=3500)
    hint: bool = False
    revealed: bool = False


class CreateIn(BaseModel):
    mode: str
    topic: str = Field(default="", max_length=200)
    project_id: str = ""
    difficulty: str = "Basics"
    budget: int = Field(default=5, ge=1, le=10)
    coach: bool = True
    spoken: bool = False
    weak_areas: str = Field(default="", max_length=1000)
    probe_claims: bool = False
    consent: bool = False


class ActIn(BaseModel):
    text: str = Field(default="", max_length=3500)
    follow: bool = False


@router.get("/practice/focus")
def focus(rec=Depends(record), c: Core = Depends(core)):
    return practice.focus_list(c, rec)


@router.post("/practice/answer")
def answer(body: AnswerIn, rec=Depends(record), c: Core = Depends(core)):
    return stream_job(lambda progress: practice.answer(c, rec, body.slot, body.index, body.attempt_id, body.text, body.hint, body.revealed, progress))


@router.get("/practice/attempts")
def attempts(rec=Depends(record), c: Core = Depends(core)):
    return practice.attempts(c, rec)


@router.get("/interviews/options")
def options(rec=Depends(record), c: Core = Depends(core)):
    return interviews.options(c, rec)


@router.get("/interviews")
def list_interviews(rec=Depends(record), c: Core = Depends(core)):
    return interviews.list_sessions(c, rec)


@router.post("/interviews")
def create_interview(body: CreateIn, rec=Depends(record), c: Core = Depends(core)):
    return stream_job(lambda progress: interviews.create(c, rec, body, progress))


@router.get("/interviews/{sid}")
def get_interview(sid: str, rec=Depends(record), c: Core = Depends(core)):
    return interviews.view(interviews.load(c, rec, sid))


@router.get("/interviews/{sid}/report")
def get_report(sid: str, rec=Depends(record), c: Core = Depends(core)):
    return interviews.report_view(c, rec, sid)


@router.post("/interviews/{sid}/transcribe")
def transcribe_answer(sid: str, file: UploadFile = File(...), rec=Depends(record), c: Core = Depends(core)):
    data = file.file.read(c.settings.audio_mb * 1024**2 + 1)
    return interviews.transcribe_turn(c, rec, sid, data)


@router.post("/interviews/{sid}/evaluate")
def evaluate_answer(sid: str, rec=Depends(record), c: Core = Depends(core)):
    return stream_job(lambda progress: interviews.evaluate_turn(c, rec, sid, progress))


@router.post("/interviews/{sid}/{action}")
def act(sid: str, action: str, body: ActIn | None = None, rec=Depends(record), c: Core = Depends(core)):
    body = body or ActIn()
    return interviews.act(c, rec, sid, action, body.text, body.follow)


@router.delete("/interviews/{sid}")
def delete_interview(sid: str, confirm: bool = False, rec=Depends(record), c: Core = Depends(core)):
    interviews.delete(c, rec, sid, confirm)
    return {"deleted": True}
