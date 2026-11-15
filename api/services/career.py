"""Career intelligence: repo insights, knowledge graph, readiness and risk signals."""
from api.errors import NotFound
from api.services import wiki
from api.services.lessons import find_project
from datetime import date, datetime

from core.career import claims as claims_mod
from core.career import graph as g
from core.career import repo as repo_mod
from core.career import security as sec
from core.career import signals as sig
from core.export import parse_item
from core.learning import Learning


def _facts(core, record):
    return {r["project_id"]: r["facts"] for r in repo_mod.Repos(core.store).all(record.id)}


def graph(core, record):
    return g.build(record.profile, _facts(core, record))


def overview(core, record):
    """One card per project: attached repo summary (if any) plus claim checks against the code."""
    repos = {r["project_id"]: r for r in repo_mod.Repos(core.store).all(record.id)}
    built = g.build(record.profile, {pid: r["facts"] for pid, r in repos.items()})
    cards = []
    for project in record.profile.projects:
        r = repos.get(project.id)
        cards.append({"project_id": project.id, "title": project.title, "repo": r,
                      "unsupported": [u["technology"] for u in built["unsupported"] if u["project_id"] == project.id],
                      "undeclared": [u["technology"] for u in built["undeclared"] if u["project_id"] == project.id]})
    return cards


def attach(core, record, project_id, url, identities, force, progress):
    find_project(record.profile, project_id)
    view, changed = repo_mod.index(core.store, record.id, project_id, url, identities=identities, force=force, progress=progress)
    return {"changed": changed, "repo": view}


def identify(core, record, project_id, identities):
    find_project(record.profile, project_id)
    return repo_mod.set_identities(core.store, record.id, project_id, [i.strip() for i in identities if i.strip()])


def detach(core, record, project_id):
    find_project(record.profile, project_id)
    repo_mod.Repos(core.store).remove(record.id, project_id)
    return {"removed": True}


def signals(core, record):
    return sig.compute(core, record, graph(core, record))


def study_first(core, record, limit):
    return sig.study_first(signals(core, record), limit)


def blast(core, record, topic):
    built = graph(core, record)
    if "concept:" + topic not in {n["id"] for n in built["nodes"]}:
        raise NotFound("That concept is not in your graph yet.")
    out = g.blast_radius(built, topic)
    out["questions"] = sig.question_count(core, record, {topic, *out["concepts"]})
    return out


HIGH_RISK, MASTERED = 6.0, 7.5


def _days_to_interview(core, record):
    """From the learning settings date if set, otherwise the saved preparation plan. None when unknown or past."""
    target = None
    setting = Learning(core.store, record.id).settings().get("interview")
    if setting:
        try:
            target = datetime.strptime(setting, "%Y-%m-%d")
        except ValueError:
            pass
    plan = core.store.item(record.id, "plan")
    if target is None and plan:
        target = parse_item(plan).inputs.interview
    days = (target.date() - date.today()).days if target else None
    return days if days is not None and days >= 0 else None


def summary(core, record):
    s = signals(core, record)
    topics = s["topics"]
    return {
        "readiness": {"overall": s["overall"], "assessed": s["assessed"], "total": s["total"]},
        "mastered": sum(1 for t in topics if t["readiness"] is not None and t["readiness"] >= MASTERED),
        "high_risk": sum(1 for t in topics if t["risk"] >= HIGH_RISK),
        "days_to_interview": _days_to_interview(core, record),
        "study_first": sig.study_first(s, 5),
        "repos": len(repo_mod.Repos(core.store).all(record.id)), "projects": len(record.profile.projects),
        "stale_pages": wiki.stale_count(core, record),
    }


def claims(core, record):
    return claims_mod.rows(record.profile, _facts(core, record), signals(core, record))


REMEDIATION = ["Rotate the exposed key or password first: assume it is already compromised.",
               "Move it to an environment variable or a secrets manager and add the file to .gitignore.",
               "Remove it from git history (for example with git filter-repo or BFG), then force-push."]


def security(core, record):
    """Per project: committed-secret findings (values masked) and the security questions its stack invites."""
    repos = {r["project_id"]: r for r in repo_mod.Repos(core.store).all(record.id)}
    out = []
    for project in record.profile.projects:
        r = repos.get(project.id)
        stack = [t["name"] for t in r["facts"]["technologies"]] if r else []
        stack += [t for t in (g_canon(x) for x in project.technologies) if t not in stack]
        out.append({"project_id": project.id, "title": project.title, "has_repo": r is not None, "url": r["url"] if r else None,
                    "secrets": r["secrets"] if r else [], "questions": sec.questions(stack, bool(r and r["secrets"]))})
    return {"projects": out, "remediation": REMEDIATION}


def g_canon(name):
    from core.career.ontology import canon
    return canon(name)
