"""Claim check, project pitch and architecture diagram share one shape: build a request, load or generate, show."""
import json

from api.errors import NotFound
from api.services.lessons import find_project
from core.career import decisions as decisions_mod
from core.career import repo as repo_mod
from core.export import claims_markdown, decisions_markdown, diagram_markdown, pitch_markdown
from core.material import claims_request, decisions_request, diagram_request, pitch_request
from core.review import ClaimTicks
from core.schemas import ClaimReport, DecisionSet, Diagram, Pitch

KINDS = {
    "claims": {"schema": ClaimReport, "project": False},
    "pitch": {"schema": Pitch, "project": True},
    "diagram": {"schema": Diagram, "project": True},
    "decisions": {"schema": DecisionSet, "project": True},
}


def _decisions(core, record, project):
    repo = repo_mod.Repos(core.store).get(record.id, project.id)
    if repo is None:
        raise ValueError("Attach this project's GitHub repository first (Learn → Projects).")
    root = repo_mod.REPOS / record.id / project.id
    if not root.is_dir():
        raise ValueError("The downloaded copy of the repository is missing. Refresh it under Learn → Projects.")
    found = decisions_mod.candidates(root, repo["identities"], [t["name"] for t in repo["facts"]["technologies"]])
    if not (found["commits"] or found["readme"]):
        raise ValueError("This repository has no README and no decision-like commits yet, so there is nothing to mine.")
    return decisions_request(record.profile, project, found)


def build_request(profile, kind, project_id, core=None, record=None):
    if kind not in KINDS:
        raise NotFound("Unknown tool.")
    if kind == "claims":
        if not (profile.projects or profile.work_experience):
            raise ValueError("Add a project or work experience in Resume and profile first.")
        return claims_request(profile)
    project = find_project(profile, project_id)
    if kind == "decisions":
        return _decisions(core, record, project)
    return (pitch_request if kind == "pitch" else diagram_request)(profile, project)


def state(core, record, kind, project_id=""):
    request = build_request(record.profile, kind, project_id, core, record)
    item = core.store.item(record.id, request.slot)
    current = item is not None and core.material.current(record, request, item)
    out = {"kind": kind, "title": request.title, "status": "current" if current else "outdated" if item else "none",
           "model": item.model if item else None, "digest": item.digest if item else None,
           "data": json.loads(item.body) if item else None}
    if kind == "claims":
        out["ticked"] = sorted(ClaimTicks(core.store).get(record.id, item.digest)) if item else []
    return out


def run(core, record, kind, project_id, regenerate, progress):
    request = build_request(record.profile, kind, project_id, core, record)
    core.material.generate(record, request, regenerate=regenerate, progress=progress)
    return state(core, record, kind, project_id)


def tick(core, record, digest, index, on):
    request = build_request(record.profile, "claims", "")
    item = core.store.item(record.id, request.slot)
    if item is None or item.digest != digest:
        raise ValueError("This claim check changed. Reload it and try again.")
    if not 0 <= index < len(ClaimReport.model_validate_json(item.body).claims):
        raise ValueError("Unknown claim.")
    ClaimTicks(core.store).set(record.id, digest, index, on)
    return {"ticked": sorted(ClaimTicks(core.store).get(record.id, digest))}


def export(core, record, kind, project_id):
    s = state(core, record, kind, project_id)
    if s["data"] is None:
        raise ValueError("Generate this first, then download it.")
    obj = KINDS[kind]["schema"].model_validate(s["data"])
    if kind == "claims":
        return claims_markdown(obj, set(s["ticked"]))
    return {"pitch": pitch_markdown, "diagram": diagram_markdown, "decisions": decisions_markdown}[kind](s["title"], obj)
