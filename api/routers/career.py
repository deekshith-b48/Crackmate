"""Career intelligence endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import Core, core
from api.routers.learn import record
from api.services import career, wiki
from api.streaming import stream_job

router = APIRouter(prefix="/api/profiles/{pid}/career")


class AttachIn(BaseModel):
    project_id: str
    url: str = Field(max_length=300)
    identities: list[str] | None = Field(default=None, max_length=10)
    force: bool = False


class IdentityIn(BaseModel):
    identities: list[str] = Field(max_length=10)


@router.get("/overview")
def overview(rec=Depends(record), c: Core = Depends(core)):
    return career.overview(c, rec)


@router.post("/repos")
def attach(body: AttachIn, rec=Depends(record), c: Core = Depends(core)):
    return stream_job(lambda progress: career.attach(c, rec, body.project_id, body.url, body.identities, body.force, progress))


@router.put("/repos/{project_id}/identity")
def identify(project_id: str, body: IdentityIn, rec=Depends(record), c: Core = Depends(core)):
    return career.identify(c, rec, project_id, body.identities)


@router.delete("/repos/{project_id}")
def detach(project_id: str, rec=Depends(record), c: Core = Depends(core)):
    return career.detach(c, rec, project_id)


@router.get("/graph")
def get_graph(rec=Depends(record), c: Core = Depends(core)):
    return career.graph(c, rec)


class RefreshIn(BaseModel):
    limit: int = Field(default=4, ge=1, le=12)


@router.get("/wiki")
def get_wiki(rec=Depends(record), c: Core = Depends(core)):
    return wiki.pages(c, rec)


@router.post("/wiki/refresh")
def refresh_wiki(body: RefreshIn, rec=Depends(record), c: Core = Depends(core)):
    return stream_job(lambda progress: wiki.refresh(c, rec, body.limit, progress))


@router.get("/summary")
def get_summary(rec=Depends(record), c: Core = Depends(core)):
    return career.summary(c, rec)


@router.get("/claims")
def get_claims(rec=Depends(record), c: Core = Depends(core)):
    return career.claims(c, rec)


@router.get("/security")
def get_security(rec=Depends(record), c: Core = Depends(core)):
    return career.security(c, rec)


@router.get("/signals")
def get_signals(rec=Depends(record), c: Core = Depends(core)):
    return career.signals(c, rec)


@router.get("/study-first")
def get_study_first(limit: int = 5, rec=Depends(record), c: Core = Depends(core)):
    return career.study_first(c, rec, max(1, min(limit, 20)))


@router.get("/blast")
def get_blast(topic: str, rec=Depends(record), c: Core = Depends(core)):
    return career.blast(c, rec, topic)
