"""Lessons: project sections and skill topics. Logic from ui/common.generator and ui/lessons.py."""
from api.errors import NotFound
from core.export import evidence_markdown, lesson_sections, parse_item
from core.learning import Learning
from core.material import (
    COMMON_TOPICS, CORE_TOPICS, LEVELS, SECTIONS, generate_many, project_request, skill_request, topics,
)
from core.review import question_id


def find_project(profile, project_id):
    project = next((p for p in profile.projects if p.id == project_id), None)
    if project is None:
        raise NotFound("This project no longer exists.")
    return project


def resolve(profile, kind, project_id="", section="", topic="", level=""):
    if kind == "project":
        if section not in SECTIONS:
            raise ValueError("Choose a valid project section.")
        return project_request(profile, find_project(profile, project_id), section)
    if kind == "skill":
        if level not in LEVELS or not topic.strip() or len(topic) > 200:
            raise ValueError("Choose a topic and a level.")
        return skill_request(profile, topic.strip(), level)
    raise ValueError("Unknown lesson type.")


def _questions(slot, questions):
    return [{"question": q.question, "answer": q.answer, "hint": q.hint, "qid": question_id(slot, q.question)} for q in questions]


def item_view(core, record, item):
    lesson = parse_item(item)
    return {
        "slot": item.slot, "title": item.title, "model": item.model, "kind": item.kind,
        "completed": core.store.completed(record.id, item),
        "sections": [{"label": label, "body": body} for label, body in lesson_sections(lesson)],
        "questions": _questions(item.slot, lesson.questions),
        "follow_ups": _questions(item.slot, getattr(lesson, "follow_ups", [])),
        "exercise": lesson.exercise,
        "assumptions": getattr(lesson, "assumptions", None),
        "evidence_note": evidence_markdown(lesson),
        "passages": lesson.evidence,
    }


def state(core, record, request):
    item = core.store.item(record.id, request.slot)
    current = item is not None and core.material.current(record, request, item)
    shared = not current and core.material.shared_body(request) is not None
    status = "current" if current else "outdated" if item else "shared" if shared else "none"
    return {
        "slot": request.slot, "title": request.title, "status": status, "shared_available": shared,
        "can_tailor": request.kind == "skill", "item": item_view(core, record, item) if item else None,
    }


def generate(core, record, request, regenerate, tailor, progress):
    item, fresh = core.material.generate(record, request, regenerate=regenerate, tailor=tailor, progress=progress)
    return state(core, record, request) | {"fresh": fresh}


def generate_all(core, record, project_id, progress):
    project = find_project(record.profile, project_id)
    requests = [project_request(record.profile, project, name) for name in SECTIONS]
    done, failed = generate_many(core.material, record, requests, progress=progress)
    return {"done": done, "failed": failed}


def project_overview(core, record, project_id):
    project = find_project(record.profile, project_id)
    rows = []
    for name, scope in SECTIONS.items():
        request = project_request(record.profile, project, name)
        item = core.store.item(record.id, request.slot)
        current = item is not None and core.material.current(record, request, item)
        rows.append({"section": name, "scope": scope, "slot": request.slot,
                     "status": "current" if current else "outdated" if item else "none",
                     "completed": bool(item) and current and core.store.completed(record.id, item)})
    return rows


def set_completed(core, record, request, completed):
    item = core.store.item(record.id, request.slot)
    if item is None or not core.material.current(record, request, item):
        raise ValueError("Load the current lesson before marking it complete.")
    core.store.mark_completed(record, item, completed)
    return state(core, record, request)


def topic_list(core, record):
    profile_topics = topics(record.profile)
    core_names, common_names = set(CORE_TOPICS), set(COMMON_TOPICS)
    catalogue = [t["name"] for t in Learning(core.store, record.id).topics()]
    groups = {"From your resume": [t for t in profile_topics if t not in core_names | common_names],
              "Core topics": list(CORE_TOPICS), "Common topics": list(COMMON_TOPICS)}
    seen = set().union(*map(set, groups.values()))
    groups["Your catalogue"] = [n for n in dict.fromkeys(catalogue) if n not in seen]
    return {"levels": list(LEVELS), "sections": SECTIONS,
            "groups": [{"title": title, "topics": names} for title, names in groups.items() if names],
            "shared_lessons": core.material.cache.count()}


def lesson_href(slot):
    """Where a saved lesson slot lives in the web app (replaces ui/plan.py: jump_to)."""
    kind, primary, secondary = slot.split(":", 2)
    if kind == "project":
        return f"/learn/projects/?project={primary}&section={secondary}"
    return f"/learn/skills/?topic={secondary}&level={primary}"
