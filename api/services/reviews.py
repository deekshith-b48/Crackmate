"""Spaced-repetition ratings and the follow-up ladder for a question."""
from core.material import ladder_request
from core.review import GRADES, Reviews, question_id
from core.schemas import Ladder


def due(core, record):
    return Reviews(core.store).due(record.id)


def rate(core, record, slot, question, answer, hint, grade):
    if grade not in GRADES:
        raise ValueError("Choose Again, Hard, Good or Easy.")
    days = Reviews(core.store).rate(record.id, slot, question, answer, hint, grade)
    return {"days": days, "message": "Due again today." if days == 0 else f"Next review in {days} day(s)."}


def _request(record, slot, question, answer):
    return ladder_request(record.profile, slot, question_id(slot, question), question, answer)


def ladder_state(core, record, slot, question, answer):
    request = _request(record, slot, question, answer)
    item = core.store.item(record.id, request.slot)
    current = item is not None and core.material.current(record, request, item)
    return {"status": "current" if current else "outdated" if item else "none",
            "steps": Ladder.model_validate_json(item.body).model_dump()["steps"] if current else None}


def build_ladder(core, record, slot, question, answer, progress):
    request = _request(record, slot, question, answer)
    item = core.store.item(record.id, request.slot)
    core.material.generate(record, request, regenerate=bool(item), progress=progress)
    return ladder_state(core, record, slot, question, answer)
