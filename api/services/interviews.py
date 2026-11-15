"""The interview state machine, moved out of ui/interview.py. Reference answers stay hidden during simulation."""
import hashlib

from api.errors import NotFound
from api.services.practice import feedback_view
from core.interview import (
    MODES, Interviews, QuestionPlan, Session, Turn, advance, confirm, evaluate, report,
)
from core.material import LEVELS, claims_request, topics
from core.review import ClaimTicks
from core.schemas import ClaimReport
from core.speech import transcribe

DIMENSIONS = ("accuracy", "coverage", "reasoning", "clarity")


def open_claims(core, record, limit=6):
    """Medium and high-risk claims from the current claim check that you have not ticked as defended."""
    request = claims_request(record.profile)
    item = core.store.item(record.id, request.slot)
    if not item or not core.material.current(record, request, item):
        return []
    done = ClaimTicks(core.store).get(record.id, item.digest)
    claims = ClaimReport.model_validate_json(item.body).claims
    return [{"claim": c.claim, "likely_question": c.probe} for i, c in enumerate(claims) if i not in done and c.risk != "low"][:limit]


def options(core, record):
    return {"modes": list(MODES), "levels": list(LEVELS), "topics": topics(record.profile),
            "projects": [{"id": p.id, "title": p.title} for p in record.profile.projects],
            "open_claims": len(open_claims(core, record)), "audio_seconds": core.settings.audio_seconds,
            "audio_mb": core.settings.audio_mb}


def _repo(core):
    return Interviews(core.store)


def load(core, record, sid):
    session = _repo(core).get(sid, record.id)
    if session is None:
        raise NotFound("This interview no longer exists.")
    return session


def summary(session):
    return {"id": session.id, "mode": session.mode, "topic": session.topic, "difficulty": session.difficulty,
            "state": session.state, "index": session.index, "budget": session.budget}


def list_sessions(core, record):
    return [summary(s) for s in _repo(core).list(record.id)]


def view(session):
    out = summary(session) | {"coach": session.coach, "spoken": session.spoken, "project_id": session.project_id}
    if session.state in ("completed", "abandoned"):
        return out | {"turn": None}
    turn = session.turns[session.index]
    behavioural = turn.question.kind == "behavioural"
    out["turn"] = {
        "id": turn.id, "question": turn.question.question, "kind": turn.question.kind, "depth": turn.depth,
        "hint": turn.question.hint if turn.hint_used else None, "hint_used": turn.hint_used,
        "original": turn.original, "confirmed": turn.confirmed, "retries": len(turn.retries),
        "has_feedback": turn.feedback is not None,
        # The example answer and, in simulation mode, the feedback stay hidden until the interview ends.
        "feedback": feedback_view(turn.feedback, behavioural) if turn.feedback and session.coach else None,
        "can_follow_up": turn.depth == 0 and session.index + 1 < session.budget,
    }
    return out


def create(core, record, body, progress):
    if not body.consent:
        raise ValueError("Confirm the provider disclosure before starting.")
    if body.mode not in MODES:
        raise ValueError("Choose an interview mode.")
    if body.mode == "Project deep-dive" and not any(p.id == body.project_id for p in record.profile.projects):
        raise ValueError("Select a project for this mode.")
    topic = {"DSA reasoning": "Data structures and algorithms", "System design": "System design fundamentals"}.get(body.mode, body.topic)
    claims = open_claims(core, record) if body.probe_claims else []
    context = {
        "mode": body.mode, "topic": topic, "difficulty": body.difficulty, "count": body.budget,
        "weak_areas": body.weak_areas, "role": record.profile.role, "company": record.profile.company,
        "project": [p.model_dump(exclude={"id", "reference"}) for p in record.profile.projects if p.id == body.project_id],
        "claims_to_probe": claims,
        "completed_lessons": [i.title for i in core.store.items(record.id) if core.store.completed(record.id, i)],
    }

    def validate(plan):
        if len(plan.questions) != body.budget or len({q.question for q in plan.questions}) != body.budget:
            raise ValueError("Return the requested number of distinct questions.")

    plan, _ = core.service.generate("interview_plan", context, QuestionPlan, validate=validate, progress=progress)
    session = Session(profile_id=record.id, mode=body.mode, topic=topic, project_id=body.project_id, difficulty=body.difficulty,
                      budget=body.budget, coach=body.coach, spoken=body.spoken,
                      turns=[Turn(question=q) for q in plan.questions], context=context)
    _repo(core).create(session)
    return view(session)


def act(core, record, sid, action, text="", follow=False):
    """Every button in the interview room that does not call a model."""
    repo, session = _repo(core), load(core, record, sid)
    turn = session.turns[min(session.index, len(session.turns) - 1)]
    if action == "pause" and session.state not in ("completed", "abandoned", "paused"):
        session.resume_state, session.state = session.state, "paused"
    elif action == "resume" and session.state == "paused":
        session.state = session.resume_state
    elif action in ("end", "abandon") and session.state not in ("completed", "abandoned"):
        session.state = "completed" if action == "end" else "abandoned"
    elif action == "hint":
        turn.hint_used = True
    elif action == "coach":
        session.coach = True
    elif action == "confirm":
        confirm(session, text)
    elif action == "idk":
        confirm(session, "I don't know.")
    elif action == "skip":
        advance(session, skip=True)
    elif action == "next":
        advance(session, follow=follow)
    elif action == "retry":
        if not turn.feedback:
            raise ValueError("There is no answer to retry yet.")
        turn.retries.append(turn.feedback)
        turn.previous_answers.append(turn.confirmed)
        turn.feedback, turn.confirmed, turn.original, turn.recording_hash, turn.outcome = None, "", "", "", "pending"
        session.state = "question ready"
    else:
        raise ValueError("That action is not available right now.")
    return view(repo.save(session))


def transcribe_turn(core, record, sid, data):
    session = load(core, record, sid)
    turn = session.turns[session.index]
    digest = hashlib.sha256(data).hexdigest()
    if not (turn.recording_hash == digest and turn.original):  # the same recording is never sent twice
        text = transcribe(data, core.settings)
        turn.original, turn.recording_hash, turn.confirmed = text, digest, ""
        session.state = "transcript review"
        session = _repo(core).save(session)
    return view(session)


def evaluate_turn(core, record, sid, progress):
    session = load(core, record, sid)
    return view(evaluate(_repo(core), core.service, record, session, progress))


def delete(core, record, sid, confirmed):
    load(core, record, sid)
    if not confirmed:
        raise ValueError("Confirm that you want to permanently delete this interview.")
    _repo(core).delete(sid, record.id)


def report_view(core, record, sid):
    session = load(core, record, sid)
    answered = [t for t in session.turns if t.feedback]
    scores = []
    for kind, labels in (("technical", ("Technical accuracy", "Coverage", "Reasoning and trade-offs", "Clarity")),
                         ("behavioural", ("Relevance", "Specificity", "Structure", "Reflection"))):
        subset = [t for t in answered if t.question.kind == kind]
        scores += [{"label": label, "average": round(sum(getattr(t.feedback, d).score for t in subset) / len(subset), 2), "count": len(subset)}
                   for d, label in zip(DIMENSIONS, labels)] if subset else []
    weakest = sorted(answered, key=lambda t: sum(getattr(t.feedback, d).score for d in DIMENSIONS))[:3]
    study = []
    for turn in weakest:
        topic = turn.topic or session.topic
        level = turn.difficulty if turn.difficulty in LEVELS else "Basics"
        href = (f"/learn/projects/?project={session.project_id}&section=Engineering%20decisions" if session.project_id
                else f"/learn/skills/?topic={topic}&level={level}")
        study.append({"topic": topic, "href": href})
    return {"state": session.state, "markdown": report(session), "scores": scores, "study_next": study,
            "scored": len(answered), "skipped": sum(t.outcome == "skipped" for t in session.turns)}
