"""The study wiki: every page CrackMate can write for you, with a freshness badge and the reason when it is stale."""
from api.services.lessons import find_project
from core.career import repo as repo_mod
from core.freshness import check
from core.material import SECTIONS, claims_request, diagram_request, pitch_request, project_request, skill_request

PROJECT_PAGES = {"pitch": ("Project pitch", pitch_request, "/learn/pitch/"), "diagram": ("Architecture diagram", diagram_request, "/learn/architecture/")}


def _row(core, record, request, group, title, kind, href):
    item = core.store.item(record.id, request.slot)
    status, why = check(core.material, record, request, item)
    return {"slot": request.slot, "group": group, "title": title, "kind": kind, "status": status, "why": why,
            "model": item.model if item else None, "href": href}


def pages(core, record):
    profile, rows = record.profile, []
    repos = {r["project_id"] for r in repo_mod.Repos(core.store).all(record.id)}
    for project in profile.projects:
        for section in SECTIONS:
            rows.append(_row(core, record, project_request(profile, project, section), project.title, section, "Project section",
                             f"/learn/projects/?project={project.id}&section={section}"))
        for _, (label, build, href) in PROJECT_PAGES.items():
            rows.append(_row(core, record, build(profile, project), project.title, label, label, href))
        if project.id in repos:
            from api.services.artifacts import build_request
            try:
                request = build_request(profile, "decisions", project.id, core, record)
                rows.append(_row(core, record, request, project.title, "Decisions from your code", "Decisions", "/analyse/decisions/"))
            except ValueError:
                pass  # nothing to mine yet
    if profile.projects or profile.work_experience:
        rows.append(_row(core, record, claims_request(profile), "Resume", "Claim check", "Claim check", "/learn/claims/"))
    for item in core.store.items(record.id):
        if item.kind == "skill":
            _, level, topic = item.slot.split(":", 2)
            rows.append(_row(core, record, skill_request(profile, topic, level), "Skills", f"{topic} · {level}", "Skill lesson",
                             f"/learn/skills/?topic={topic}&level={level}"))
    return rows


def stale_count(core, record):
    """Cheap enough for the dashboard: only pages that already exist are checked."""
    return sum(1 for r in pages(core, record) if r["status"] == "stale")


def refresh(core, record, limit, progress):
    """Rewrite stale pages (never pages that do not exist yet). Capped so one click cannot burn the free-tier budget."""
    from api.services.artifacts import build_request
    profile = record.profile
    stale = [r for r in pages(core, record) if r["status"] == "stale"]
    done, failed = 0, []
    for row in stale[:limit]:
        progress(f"Rewriting {row['group']} · {row['title']}…")
        try:
            kind, *rest = row["slot"].split(":")
            if kind == "project":
                request = project_request(profile, find_project(profile, rest[0]), rest[1])
            elif kind in ("pitch", "diagram", "decisions"):
                request = build_request(profile, kind, rest[0], core, record)
            elif kind == "claims":
                request = claims_request(profile)
            else:
                request = skill_request(profile, rest[1], rest[0])
            core.material.generate(record, request, regenerate=True, progress=lambda _: None)
            done += 1
        except Exception as exc:  # noqa: BLE001 - one failing page must not stop the rest; the reason is reported
            failed.append(f"{row['title']}: {exc}")
            if "rate limit" in str(exc).lower():
                break  # the free-tier budget is spent: stop instead of failing every remaining page
    return {"refreshed": done, "failed": failed, "remaining": max(0, len(stale) - done - len(failed))}
