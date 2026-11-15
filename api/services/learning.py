"""Track: readiness, study queue, topic progress, learning settings and the adaptive seven-day plan (ui/learning.py)."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from api.errors import NotFound
from core.learning import Learning, export_progress, readiness, utcnow

_PROPOSALS = {}  # profile id -> last proposal, kept on the server so the browser cannot tamper with it


def _learning(core, record):
    learning = Learning(core.store, record.id)
    learning.sync()
    return learning


def _tomorrow(learning, now):
    return (now.astimezone(ZoneInfo(learning.settings()["timezone"])).date() + timedelta(days=1)).isoformat()


def progress(core, record):
    learning, now = _learning(core, record), utcnow()
    rows = learning.progress(now)
    overall, assessed, total, scores = readiness(rows)
    return {"readiness": {"overall": overall, "assessed": assessed, "total": total},
            "topics": [{"id": t["id"], "name": t["name"], "category": t["category"], "state": t["state"], "due": t["due"],
                        "count": t["count"], "readiness": scores[t["id"]]} for t in rows]}


def topic_detail(core, record, tid):
    learning, now = _learning(core, record), utcnow()
    topic = next((t for t in learning.progress(now) if t["id"] == tid), None)
    if topic is None:
        raise NotFound("This topic no longer exists.")
    return {"id": tid, "name": topic["name"], "state": topic["state"], "due": topic["due"], "count": topic["count"],
            "limitation": topic["limitation"],
            "evidence": [{"question": e["question"], "source": e["source"], "time": e["time"], "scores": e["scores"],
                          "missing": e["missing"], "independent": e["independent"]} for e in topic["evidence"]]}


def topic_action(core, record, tid, action):
    learning, now = _learning(core, record), utcnow()
    if tid not in {t["id"] for t in learning.topics()}:
        raise NotFound("This topic no longer exists.")
    today = now.astimezone(ZoneInfo(learning.settings()["timezone"])).date().isoformat()
    if action == "review_tomorrow":
        learning.preference("due:" + tid, _tomorrow(learning, now))
    elif action == "reset_progress":
        learning.preference("reset:" + tid, now.isoformat())
        learning.preference("due:" + tid, None)
    elif action == "reset_schedule":
        learning.preference("due:" + tid, today)
    else:
        raise ValueError("That action is not available.")
    return topic_detail(core, record, tid)


def queue(core, record, minutes):
    learning = _learning(core, record)
    return learning.queue(utcnow(), minutes or learning.settings()["daily_minutes"])


def queue_action(core, record, tid, action):
    learning, now = _learning(core, record), utcnow()
    if tid not in {t["id"] for t in learning.topics()}:
        raise NotFound("This topic no longer exists.")
    choice = {"pin": {"pinned": True}, "tomorrow": {"postpone": _tomorrow(learning, now)}, "dismiss": {"dismissed": True}}.get(action)
    if choice is None:
        raise ValueError("That action is not available.")
    learning.preference("queue:" + tid, choice)
    return {"ok": True}


def restore_queue(core, record):
    learning = _learning(core, record)
    for topic in learning.topics():
        learning.preference("queue:" + topic["id"], {})
    return {"ok": True}


def get_settings(core, record):
    learning = Learning(core.store, record.id)
    return {"settings": learning.settings(), "topics": [{"id": t["id"], "name": t["name"]} for t in learning.topics()]}


def save_settings(core, record, s):
    try:
        ZoneInfo(s.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Choose an IANA timezone such as Asia/Kolkata.") from None
    dates = [d.strip() for d in s.unavailable if d.strip()]
    for date in dates + ([s.interview] if s.interview else []):
        datetime.strptime(date, "%Y-%m-%d")
    sequence = s.intervals
    if not sequence or sequence != sorted(sequence) or min(sequence) < 1 or max(sequence) > 365:
        raise ValueError("Use increasing review intervals from 1 to 365 days.")
    learning = Learning(core.store, record.id)
    learning.preference("settings", dict(timezone=s.timezone, interview=s.interview, daily_minutes=s.daily_minutes,
                                         session_minutes=s.session_minutes, unavailable=dates, priorities=s.priorities,
                                         threshold=s.threshold, successes=s.successes, intervals=sequence))
    return get_settings(core, record)


def propose(core, record):
    proposal = _learning(core, record).propose(utcnow())
    _PROPOSALS[record.id] = proposal
    return {"id": proposal["id"], "reason": proposal["reason"], "blocks": proposal["blocks"],
            "active_count": len(Learning(core.store, record.id).active_plan().get("blocks", []))}


def apply(core, record, proposal_id):
    proposal = _PROPOSALS.get(record.id)
    if not proposal or proposal["id"] != proposal_id:
        raise ValueError("That proposal expired. Propose the plan again.")
    Learning(core.store, record.id).apply_plan(proposal)
    del _PROPOSALS[record.id]
    return active_plan(core, record)


def active_plan(core, record):
    return Learning(core.store, record.id).active_plan().get("blocks", [])


def update_block(core, record, block_id, completed, pinned):
    learning = Learning(core.store, record.id)
    learning.update_block(block_id, "completed", completed)
    learning.update_block(block_id, "pinned", pinned)
    return active_plan(core, record)


def export(core, record):
    return export_progress(_learning(core, record), utcnow())
