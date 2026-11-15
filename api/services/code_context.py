"""Facts read from a project's real repository, added to its lessons so questions are about what you built.

Because the commit is part of the context, a new commit changes the lesson's fingerprint: the page shows as stale.
"""
from dataclasses import replace

from core.career import repo as repo_mod

PROJECT_KINDS = {"project", "pitch", "diagram", "decisions"}
NOTE = ("Facts read from the candidate's real repository, not from the resume. Use them to ask about what they built. "
        "Anything beyond them is an assumption and must be labelled (Assumption).")


def for_project(store, profile_id, project_id):
    repo = repo_mod.Repos(store).get(profile_id, project_id)
    if repo is None:
        return None
    own = repo["ownership"]
    return {"note": NOTE, "repo": repo["url"], "commit": repo["commit"][:7],
            "stack": [t["name"] for t in repo["facts"]["technologies"][:12]],
            "your_share": own["share"] if own["identified"] else None,
            "hotspots": [h["path"] for h in repo["hotspots"][:5]],
            "not_written_by_you": [f["path"] for f in own["files_not_yours"][:3]]}


def enrich(store, record, request):
    if request.kind not in PROJECT_KINDS:
        return request
    parts = request.slot.split(":")
    code = for_project(store, record.id, parts[1]) if len(parts) > 1 else None
    return replace(request, context={**request.context, "code": code}) if code else request
