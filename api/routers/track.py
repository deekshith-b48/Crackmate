"""Plan, Track, Knowledge Library, Company DSA and exports."""
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from api.deps import Core, core
from api.routers.learn import record
from api.services import knowledge, learning, planning
from api.services.lessons import resolve
from api.streaming import stream_job
from core import company
from core.export import NOTICE, all_markdown, item_markdown, project_markdown
from core.material import SECTIONS, lesson_requests, project_request

router = APIRouter(prefix="/api")
P = "/profiles/{pid}"


class PlanIn(BaseModel):
    interview: str
    hours: float = Field(ge=0.25, le=24)
    weak_areas: str = Field(default="", max_length=1500)
    role_context: str = Field(default="", max_length=1500)
    regenerate: bool = False


class SettingsIn(BaseModel):
    timezone: str
    interview: str = ""
    daily_minutes: int = Field(ge=5, le=240)
    session_minutes: int = Field(ge=5, le=50)
    unavailable: list[str] = []
    priorities: list[str] = []
    threshold: int = Field(ge=1, le=4)
    successes: int = Field(ge=2, le=5)
    intervals: list[int]


class ActionIn(BaseModel):
    action: str


class BlockIn(BaseModel):
    completed: bool
    pinned: bool


class ApplyIn(BaseModel):
    id: str


class ImportIn(BaseModel):
    title: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=2000)
    text: str = Field(default="", max_length=100_000)
    license: str = Field(default="Unknown", max_length=200)


def _md(text, name):
    return PlainTextResponse(text, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---- Plan
@router.get(P + "/plan")
def get_plan(rec=Depends(record), c: Core = Depends(core)):
    return planning.state(c, rec)


@router.post(P + "/plan")
def build_plan(body: PlanIn, rec=Depends(record), c: Core = Depends(core)):
    interview = datetime.fromisoformat(body.interview)
    return stream_job(lambda progress: planning.build(c, rec, interview, body.hours, body.weak_areas, body.role_context, body.regenerate, progress))


@router.get(P + "/plan/export")
def plan_export(rec=Depends(record), c: Core = Depends(core)):
    return _md(planning.export(c, rec), "crackmate-plan.md")


# ---- Track
@router.get(P + "/learning/progress")
def get_progress(rec=Depends(record), c: Core = Depends(core)):
    return learning.progress(c, rec)


@router.get(P + "/learning/topics/{tid}")
def get_topic(tid: str, rec=Depends(record), c: Core = Depends(core)):
    return learning.topic_detail(c, rec, tid)


@router.post(P + "/learning/topics/{tid}")
def topic_action(tid: str, body: ActionIn, rec=Depends(record), c: Core = Depends(core)):
    return learning.topic_action(c, rec, tid, body.action)


@router.get(P + "/learning/queue")
def get_queue(minutes: int = 0, rec=Depends(record), c: Core = Depends(core)):
    return learning.queue(c, rec, minutes)


@router.post(P + "/learning/queue/restore")
def restore_queue(rec=Depends(record), c: Core = Depends(core)):
    return learning.restore_queue(c, rec)


@router.post(P + "/learning/queue/{tid}")
def queue_action(tid: str, body: ActionIn, rec=Depends(record), c: Core = Depends(core)):
    return learning.queue_action(c, rec, tid, body.action)


@router.get(P + "/learning/settings")
def get_settings(rec=Depends(record), c: Core = Depends(core)):
    return learning.get_settings(c, rec)


@router.put(P + "/learning/settings")
def put_settings(body: SettingsIn, rec=Depends(record), c: Core = Depends(core)):
    return learning.save_settings(c, rec, body)


@router.post(P + "/learning/propose")
def propose(rec=Depends(record), c: Core = Depends(core)):
    return learning.propose(c, rec)


@router.post(P + "/learning/apply")
def apply(body: ApplyIn, rec=Depends(record), c: Core = Depends(core)):
    return learning.apply(c, rec, body.id)


@router.get(P + "/learning/plan")
def get_active_plan(rec=Depends(record), c: Core = Depends(core)):
    return learning.active_plan(c, rec)


@router.put(P + "/learning/plan/{block_id}")
def update_block(block_id: str, body: BlockIn, rec=Depends(record), c: Core = Depends(core)):
    return learning.update_block(c, rec, block_id, body.completed, body.pinned)


# ---- Exports
@router.get(P + "/export/all")
def export_all(rec=Depends(record), c: Core = Depends(core)):
    requests = {r.slot: r for r in lesson_requests(rec.profile)}
    items = c.store.items(rec.id)

    def is_current(item):
        if item.kind == "plan":
            return planning.plan_status(c, rec, item, [i for i in items if i.kind in ("project", "skill")], c.store.attempts(rec.id), datetime.now())
        return item.slot in requests and c.material.current(rec, requests[item.slot], item)

    return _md(all_markdown(rec.profile, items, is_current), "crackmate-preparation.md")


@router.get(P + "/export/lesson")
def export_lesson(kind: str, project_id: str = "", section: str = "", topic: str = "", level: str = "",
                  rec=Depends(record), c: Core = Depends(core)):
    request = resolve(rec.profile, kind, project_id, section, topic, level)
    item = c.store.item(rec.id, request.slot)
    if item is None:
        raise ValueError("Generate this lesson first, then download it.")
    return _md(NOTICE + "\n\n" + item_markdown(item, outdated=not c.material.current(rec, request, item)), "crackmate-lesson.md")


@router.get(P + "/export/project")
def export_project(project_id: str, rec=Depends(record), c: Core = Depends(core)):
    project = next((p for p in rec.profile.projects if p.id == project_id), None)
    if project is None:
        raise ValueError("Choose a project.")
    requests = {r.slot: r for r in (project_request(rec.profile, project, name) for name in SECTIONS)}
    items = [i for i in c.store.items(rec.id) if i.slot in requests]
    return _md(project_markdown(project, items, lambda i: c.material.current(rec, requests[i.slot], i)), "crackmate-project.md")


@router.get(P + "/export/learning")
def export_learning(rec=Depends(record), c: Core = Depends(core)):
    return _md(learning.export(c, rec), "crackmate-learning.md")


# ---- Knowledge Library (shared by every profile)
@router.get("/knowledge/sources")
def sources(c: Core = Depends(core)):
    return knowledge.sources(c)


@router.get("/knowledge/search")
def search(q: str = "", c: Core = Depends(core)):
    return knowledge.search(c, q)


@router.post("/knowledge/import")
def import_text(body: ImportIn, c: Core = Depends(core)):
    return knowledge.import_source(c, body.title, body.url, body.text, body.license)


@router.post("/knowledge/import-file")
def import_file(file: UploadFile = File(...), title: str = Form(""), license: str = Form("Unknown"), c: Core = Depends(core)):
    return knowledge.import_source(c, title, "", "", license, (file.filename or "", file.file.read(2_000_001)))


@router.post("/knowledge/build")
def build_base(c: Core = Depends(core)):
    return stream_job(lambda progress: knowledge.build_base(c, progress))


@router.post("/knowledge/{sid}/refresh")
def refresh(sid: str, c: Core = Depends(core)):
    return knowledge.refresh(c, sid)


@router.delete("/knowledge/{sid}")
def delete_source(sid: str, c: Core = Depends(core)):
    return knowledge.delete(c, sid)


# ---- Company DSA
@router.get("/company/list")
def company_list():
    return knowledge.company_list()


@router.get("/company/problems")
def company_problems(company_name: str, window: str = "All time", levels: str = ""):
    if window not in company.WINDOWS:
        raise ValueError("Choose a valid time window.")
    return knowledge.company_problems(company_name, window, [l for l in levels.split(",") if l])


@router.get("/company/fallback")
def company_fallback():
    return {"topics": list(company.FALLBACK_TOPICS)}
