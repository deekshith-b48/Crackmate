"""The 24-hour preparation plan, moved out of ui/plan.py."""
from datetime import datetime, time, timedelta

from api.services.lessons import lesson_href
from core.export import NOTICE, item_markdown, parse_item
from core.planning import PlanInput, plan_request


def _lessons(core, record):
    return [i for i in core.store.items(record.id) if i.kind in ("project", "skill")]


def plan_status(core, record, item, lessons, attempts, now):
    if item is None:
        return False
    plan = parse_item(item)
    if now >= plan.inputs.interview:
        return False
    try:
        request = plan_request(record.profile, plan.inputs, attempts, lessons)
    except ValueError:
        return False
    return core.material.current(record, request, item)


def state(core, record, now=None):
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    item = core.store.item(record.id, "plan")
    attempts = core.store.attempts(record.id)
    lessons = _lessons(core, record)
    previous = parse_item(item) if item else None
    default = previous.inputs if previous else None
    out = {
        "status": "none", "now": now.isoformat(timespec="minutes"),
        "defaults": {"interview": (default.interview if default else datetime.combine(now.date() + timedelta(days=1), time(10))).isoformat(timespec="minutes"),
                     "hours": default.budget / 60 if default else 2.0,
                     "weak_areas": default.weak_areas if default else "", "role_context": default.role_context if default else ""},
        "plan": None,
    }
    if not item:
        return out
    current = plan_status(core, record, item, lessons, attempts, now)
    total = sum(b.duration_minutes for b in previous.blocks)
    blocks = []
    for window, block in zip(previous.windows, previous.blocks, strict=True):
        slot = previous.links.get(block.reference)
        blocks.append({"start": window.start.isoformat(timespec="minutes"), "end": window.end.isoformat(timespec="minutes"),
                       "minutes": block.duration_minutes, "topic": block.topic, "reason": block.reason, "outcome": block.outcome,
                       "href": lesson_href(slot) if current and slot else None})
    out.update(status="current" if current else "outdated", plan={
        "interview": previous.inputs.interview.isoformat(timespec="minutes"), "total_minutes": total,
        "minutes_until": max(0, int((previous.inputs.interview - now).total_seconds() // 60)), "blocks": blocks})
    return out


def build(core, record, interview_at, hours, weak_areas, role_context, regenerate, progress, now=None):
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    item = core.store.item(record.id, "plan")
    previous = parse_item(item) if item else None
    attempts = core.store.attempts(record.id)
    lessons = _lessons(core, record)
    base_start, budget = now, round(hours * 60)
    weak, role = weak_areas.strip(), role_context.strip()
    # Keep saved windows for identical inputs or explicit regeneration before the first window expires.
    if previous and previous.inputs.interview > now:
        saved = previous.inputs
        unchanged = (interview_at, budget, weak, role) == (saved.interview, saved.budget, saved.weak_areas, saved.role_context)
        if unchanged and not regenerate and core.material.current(record, plan_request(record.profile, saved, attempts, lessons), item):
            return state(core, record, now)
        if unchanged and previous.windows and previous.windows[0].start >= now:
            base_start = saved.start
    inputs = PlanInput(start=base_start, interview=interview_at, budget=budget, weak_areas=weak_areas, role_context=role_context)
    core.material.generate(record, plan_request(record.profile, inputs, attempts, lessons), regenerate=regenerate, progress=progress)
    return state(core, record, now)


def export(core, record):
    item = core.store.item(record.id, "plan")
    if item is None:
        raise ValueError("Build a plan first, then download it.")
    now = datetime.now()
    current = plan_status(core, record, item, _lessons(core, record), core.store.attempts(record.id), now)
    return NOTICE + "\n\n" + item_markdown(item, outdated=not current)
