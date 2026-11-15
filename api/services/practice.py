"""Text practice (ui/practice.py) and the feedback layout shared with the interview room."""
from uuid import uuid4

from api.errors import NotFound
from core.export import evidence_markdown, parse_item
from core.material import lesson_requests
from core.practice import RUBRIC, SCALE, review_answer

BEHAVIOURAL = ("Relevance", "Specificity", "Structure", "Reflection")


def feedback_view(feedback, behavioural=False):
    labels = dict(zip(RUBRIC, BEHAVIOURAL)) if behavioural else RUBRIC
    return {
        "scores": [{"key": key, "label": label, "score": getattr(feedback, key).score, "reason": getattr(feedback, key).reason}
                   for key, label in labels.items()],
        "scale": SCALE, "correct": feedback.correct, "missing": feedback.missing,
        "corrected": feedback.corrected, "follow_up": feedback.follow_up,
        "evidence_note": evidence_markdown(feedback),
    }


def _current_items(core, record):
    requests = {r.slot: r for r in lesson_requests(record.profile)}
    items = {i.slot: i for i in core.store.items(record.id)
             if i.slot in requests and core.material.current(record, requests[i.slot], i)}
    return requests, items


def focus_list(core, record):
    _, items = _current_items(core, record)
    return [{"slot": slot, "title": item.title,
             "questions": [{"question": q.question, "hint": q.hint} for q in parse_item(item).questions[:3]]}
            for slot, item in items.items()]


def answer(core, record, slot, index, attempt_id, text, hint, revealed, progress):
    requests, items = _current_items(core, record)
    if slot not in items:
        raise NotFound("Generate a current lesson to unlock its practice questions.")
    questions = parse_item(items[slot]).questions[:3]
    if not 0 <= index < len(questions):
        raise ValueError("Unknown question.")
    feedback = review_answer(core.store, core.service, record, attempt_id, requests[slot], questions[index], text, progress,
                             assistance={"hint": hint, "revealed": revealed})
    return {"attempt_id": attempt_id, "feedback": feedback_view(feedback)}


def new_attempt_id():
    return uuid4().hex


def attempts(core, record):
    return [{"id": a.id, "focus": a.focus, "question": a.question, "answer": a.answer, "created_at": a.created_at,
             "feedback": feedback_view(a.feedback)} for a in core.store.attempts(record.id)]
