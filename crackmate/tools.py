"""One implementation of every command-line and MCP capability. Plain functions: (core, record, ...) -> data."""
import json
import os
from uuid import uuid4

from api.services import brief as brief_service
from api.services import career, lessons
from api.services.artifacts import state as artifact_state
from api.services.profiles import view as profile_view
from core.ask.search import hybrid
from core.career import repo as repo_mod
from core.export import clean, lesson_sections
from core.material import project_request, skill_request
from core.practice import review_answer
from core.review import Reviews, question_id
from core.schemas import ProjectLesson, SkillLesson

LEVELS = ("Basics", "Intermediate", "Advanced")


class CrackError(ValueError):
    """A problem the user can fix: shown as a plain message, never a traceback."""


def resolve_profile(core, ident=None):
    """A profile by id prefix, else CRACKMATE_PROFILE, else the most recently created one."""
    ident = ident or os.environ.get("CRACKMATE_PROFILE")
    records = core.store.profiles()
    if not records:
        raise CrackError("No profile yet. Run `crackmate init --resume resume.pdf`, or create one in the web app.")
    if ident:
        match = [r for r in records if r.id.startswith(ident)]
        if len(match) != 1:
            raise CrackError(f"No single profile starts with {ident!r}. Run `crackmate profiles` to see them.")
        return match[0]
    return records[0]


def profiles(core):
    return [{"id": r.id[:8], "name": r.profile.name or "(no name)", "role": r.profile.role or "", "projects": len(r.profile.projects)} for r in core.store.profiles()]


def profile(core, record):
    """The profile without contact details."""
    p = profile_view(record)["profile"]
    return json.loads(clean(json.dumps(p)))


def overview(core, record):
    return career.summary(core, record)


def weak_spots(core, record, n=8):
    return [{"topic": t["topic"], "risk": t["risk"], "readiness": t["readiness"], "assessed": t["assessed"], "why": t["why"][0]}
            for t in career.signals(core, record)["topics"] if t["risk"] > 0][:n]


def study_next(core, record, base="http://127.0.0.1:8000"):
    top = career.study_first(core, record, 1)
    if not top:
        return None
    t = top[0]
    has = core.store.item(record.id, f"skill:Basics:{t['topic']}") is not None or core.material.shared_body(skill_request(record.profile, t["topic"], "Basics")) is not None
    return {**t, "lesson_ready": has, "open": f"{base}/learn/skills/?topic={t['topic'].replace(' ', '%20')}&level=Basics",
            "do": f"Run `crackmate quiz --topic \"{t['topic']}\"` to practise it now." if has else f"Open {base}/learn/skills/ and generate the lesson first."}


def canonical_topic(core, record, name):
    names = [t for g in lessons.topic_list(core, record)["groups"] for t in g["topics"]]
    for n in names:
        if n.casefold() == name.strip().casefold():
            return n
    close = [n for n in names if name.casefold() in n.casefold()][:5]
    raise CrackError(f"Unknown topic {name!r}." + (f" Did you mean: {', '.join(close)}?" if close else ""))


def _body(core, record, topic, level):
    """A saved lesson, else the shared one, else None. Never calls a model."""
    item = core.store.item(record.id, f"skill:{level}:{topic}")
    if item:
        return item.body
    return core.material.shared_body(skill_request(record.profile, topic, level))


def lesson(core, record, topic, level="Basics"):
    topic = canonical_topic(core, record, topic)
    if level not in LEVELS:
        raise CrackError(f"Level must be one of {', '.join(LEVELS)}.")
    body = _body(core, record, topic, level)
    if body is None:
        return {"topic": topic, "level": level, "available": False,
                "message": "This lesson has not been generated yet. Generate it in the web app (Learn → Skills) and ask again."}
    parsed = SkillLesson.model_validate_json(body)
    return {"topic": topic, "level": level, "available": True, "sections": [{"label": l, "body": b} for l, b in lesson_sections(parsed)],
            "questions": [{"id": question_id(f"skill:{level}:{topic}", q.question), "question": q.question, "answer": q.answer} for q in parsed.questions]}


def cards(core, record, topic=None, level="Basics"):
    """Flashcards with answers: due review cards first, then questions from lessons (a topic, or your riskiest ones)."""
    out = [{"slot": c["slot"], "question": c["question"], "answer": c["answer"], "hint": c["hint"], "due": True} for c in Reviews(core.store).due(record.id)]
    topics = [canonical_topic(core, record, topic)] if topic else [t["topic"] for t in weak_spots(core, record, 6)]
    seen = {c["question"] for c in out}
    for t in topics:
        body = _body(core, record, t, level)
        for q in (SkillLesson.model_validate_json(body).questions if body else []):
            if q.question not in seen:
                out.append({"slot": f"skill:{level}:{t}", "question": q.question, "answer": q.answer, "hint": q.hint, "due": False})
    return out


def quiz_me(core, record, topic, n=3, level="Basics"):
    """Questions without answers. grade_answer takes the id back."""
    return [{"id": question_id(c["slot"], c["question"]), "topic": c["slot"].split(":", 2)[-1], "question": c["question"], "hint": c["hint"]}
            for c in cards(core, record, topic, level)[:max(1, min(n, 10))]]


def rate(core, record, card, grade):
    return Reviews(core.store).rate(record.id, card["slot"], card["question"], card["answer"], card["hint"], grade)


def _find(core, record, qid):
    """The (request, question) behind a question id: saved lessons first (fast), then the shared lesson cache."""
    for item in core.store.items(record.id):
        if item.kind == "skill":
            _, level, topic = item.slot.split(":", 2)
            for q in SkillLesson.model_validate_json(item.body).questions:
                if question_id(item.slot, q.question) == qid:
                    return skill_request(record.profile, topic, level), q
        elif item.kind == "project":
            _, pid, section = item.slot.split(":", 2)
            for q in ProjectLesson.model_validate_json(item.body).questions:
                if question_id(item.slot, q.question) == qid:
                    return project_request(record.profile, lessons.find_project(record.profile, pid), section), q
    for topic in [t for g in lessons.topic_list(core, record)["groups"] for t in g["topics"]]:
        for level in LEVELS:
            body = _body(core, record, topic, level)
            for q in (SkillLesson.model_validate_json(body).questions if body else []):
                if question_id(f"skill:{level}:{topic}", q.question) == qid:
                    return skill_request(record.profile, topic, level), q
    raise CrackError("Unknown question id. Ask quiz_me for questions first.")


def grade_answer(core, record, qid, answer):
    """Score an answer with the model (needs your Groq key). Saved as a practice attempt, so it moves your readiness."""
    if not answer.strip() or len(answer) > 3500:
        raise CrackError("Give an answer between 1 and 3,500 characters.")
    request, question = _find(core, record, qid)
    fb = review_answer(core.store, core.service, record, uuid4().hex, request, question, answer, lambda _: None)
    return {"scores": {k: getattr(fb, k).score for k in ("accuracy", "coverage", "reasoning", "clarity")}, "correct": fb.correct, "missing": fb.missing,
            "better_answer": fb.corrected, "follow_up": fb.follow_up, "scale": "0 to 4 per dimension; coaching estimates."}


def architecture(core, record, project):
    match = [p for p in record.profile.projects if project.casefold() in p.title.casefold() or p.id.startswith(project)]
    if len(match) != 1:
        raise CrackError(f"Name one project: {', '.join(p.title for p in record.profile.projects) or 'none yet'}.")
    state = artifact_state(core, record, "diagram", match[0].id)
    if state["data"] is None:
        return {"project": match[0].title, "available": False, "message": "No architecture diagram saved yet. Draw it in the web app (Learn → Architecture)."}
    return {"project": match[0].title, "available": True, "mermaid": state["data"]["diagram"], "assumptions": state["data"]["assumptions"], "status": state["status"]}


def search_knowledge(core, record, query, k=6):
    return hybrid(core, record, query, k)


def interview_brief(core, record):
    return brief_service.build(core, record)["markdown"]


def update_repos(core, record, progress=lambda _: None):
    out = []
    for r in repo_mod.Repos(core.store).all(record.id):
        _, changed = repo_mod.index(core.store, record.id, r["project_id"], r["url"], progress=progress)
        out.append({"url": r["url"], "changed": changed})
    return out
