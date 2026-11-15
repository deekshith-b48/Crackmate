"""Learn endpoints: lessons, claim checker, pitch, architecture, reviews, ladders and the dashboard."""
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from api.deps import Core, core
from api.services import artifacts, dashboard, lessons, reviews
from api.services.profiles import get_record
from api.streaming import stream_job

router = APIRouter(prefix="/api/profiles/{pid}")


def record(pid: str, c: Core = Depends(core)):
    return get_record(c, pid)


class LessonRef(BaseModel):
    kind: str
    project_id: str = ""
    section: str = ""
    topic: str = Field(default="", max_length=200)
    level: str = ""


class GenerateIn(LessonRef):
    regenerate: bool = False
    tailor: bool = False


class CompleteIn(LessonRef):
    completed: bool


class AllIn(BaseModel):
    project_id: str


class ArtifactIn(BaseModel):
    project_id: str = ""
    regenerate: bool = False


class TickIn(BaseModel):
    digest: str
    index: int
    on: bool


class RateIn(BaseModel):
    slot: str
    question: str
    answer: str
    hint: str = ""
    grade: str


class LadderIn(BaseModel):
    slot: str
    question: str
    answer: str


def _request(rec, ref: LessonRef):
    return lessons.resolve(rec.profile, ref.kind, ref.project_id, ref.section, ref.topic, ref.level)


@router.get("/dashboard")
def get_dashboard(rec=Depends(record), c: Core = Depends(core)):
    return dashboard.build(c, rec)


@router.get("/lessons/topics")
def topics(rec=Depends(record), c: Core = Depends(core)):
    return lessons.topic_list(c, rec)


@router.get("/lessons/overview")
def overview(project_id: str, rec=Depends(record), c: Core = Depends(core)):
    return lessons.project_overview(c, rec, project_id)


@router.get("/lessons")
def lesson_state(kind: str, project_id: str = "", section: str = "", topic: str = "", level: str = "",
                 rec=Depends(record), c: Core = Depends(core)):
    return lessons.state(c, rec, lessons.resolve(rec.profile, kind, project_id, section, topic, level))


@router.post("/lessons/generate")
def generate_lesson(body: GenerateIn, rec=Depends(record), c: Core = Depends(core)):
    request = _request(rec, body)
    return stream_job(lambda progress: lessons.generate(c, rec, request, body.regenerate, body.tailor, progress))


@router.post("/lessons/generate-all")
def generate_all(body: AllIn, rec=Depends(record), c: Core = Depends(core)):
    return stream_job(lambda progress: lessons.generate_all(c, rec, body.project_id, progress))


@router.post("/lessons/complete")
def complete(body: CompleteIn, rec=Depends(record), c: Core = Depends(core)):
    return lessons.set_completed(c, rec, _request(rec, body), body.completed)


@router.get("/artifacts/{kind}")
def artifact_state(kind: str, project_id: str = "", rec=Depends(record), c: Core = Depends(core)):
    return artifacts.state(c, rec, kind, project_id)


@router.post("/artifacts/{kind}/run")
def artifact_run(kind: str, body: ArtifactIn, rec=Depends(record), c: Core = Depends(core)):
    artifacts.build_request(rec.profile, kind, body.project_id, c, rec)  # fail fast, before streaming starts
    return stream_job(lambda progress: artifacts.run(c, rec, kind, body.project_id, body.regenerate, progress))


@router.get("/artifacts/{kind}/export")
def artifact_export(kind: str, project_id: str = "", rec=Depends(record), c: Core = Depends(core)):
    return PlainTextResponse(artifacts.export(c, rec, kind, project_id), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="crackmate-{kind}.md"'})


@router.put("/claims/tick")
def claim_tick(body: TickIn, rec=Depends(record), c: Core = Depends(core)):
    return artifacts.tick(c, rec, body.digest, body.index, body.on)


@router.get("/reviews/due")
def due_reviews(rec=Depends(record), c: Core = Depends(core)):
    return reviews.due(c, rec)


@router.post("/reviews/rate")
def rate(body: RateIn, rec=Depends(record), c: Core = Depends(core)):
    return reviews.rate(c, rec, body.slot, body.question, body.answer, body.hint, body.grade)


@router.post("/ladder/lookup")
def ladder_lookup(body: LadderIn, rec=Depends(record), c: Core = Depends(core)):
    return reviews.ladder_state(c, rec, body.slot, body.question, body.answer)


@router.post("/ladder/build")
def ladder_build(body: LadderIn, rec=Depends(record), c: Core = Depends(core)):
    return stream_job(lambda progress: reviews.build_ladder(c, rec, body.slot, body.question, body.answer, progress))
