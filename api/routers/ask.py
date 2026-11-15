"""Ask CrackMate and the Interview Brief."""
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from api.deps import Core, core
from api.routers.learn import record
from api.services import ask, brief
from api.streaming import stream_events

router = APIRouter(prefix="/api/profiles/{pid}")


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=4000)


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    history: list[Turn] = Field(default=[], max_length=8)


@router.post("/ask")
def ask_question(body: AskIn, rec=Depends(record), c: Core = Depends(core)):
    history = [t.model_dump() for t in body.history]
    return stream_events(lambda emit: ask.answer(c, rec, body.question, history, emit))


@router.get("/ask/status")
def ask_status(rec=Depends(record), c: Core = Depends(core)):
    return ask.status(c, rec)


@router.get("/career/brief")
def get_brief(rec=Depends(record), c: Core = Depends(core)):
    return brief.build(c, rec)


@router.get("/career/brief/export")
def export_brief(rec=Depends(record), c: Core = Depends(core)):
    return PlainTextResponse(brief.build(c, rec)["markdown"], media_type="text/markdown",
                             headers={"Content-Disposition": 'attachment; filename="crackmate-interview-brief.md"'})
