"""Deterministic study windows with generated activities assigned to each window."""
from datetime import datetime, time, timedelta

from pydantic import Field

from core.material import Request, SECTIONS, target_context, topics
from core.schemas import Data, PlanDraft, StudyBlock


BREAK = timedelta(minutes=10)
INTERVIEW_BUFFER = timedelta(minutes=15)
MAX_MINUTES = 24 * 60


class PlanInput(Data):
    start: datetime
    interview: datetime
    budget: int = Field(ge=1, le=MAX_MINUTES)
    weak_areas: str = Field(max_length=1500)
    role_context: str = Field(max_length=1500)


class Window(Data):
    start: datetime
    end: datetime

    @property
    def minutes(self):
        return int((self.end - self.start).total_seconds() // 60)


class Plan(Data):
    inputs: PlanInput
    windows: list[Window]
    blocks: list[StudyBlock]
    links: dict[str, str]


def build_windows(start, interview, budget):
    if interview <= start:
        raise ValueError("Choose a future interview date and time.")
    end = interview - INTERVIEW_BUFFER
    windows = []
    cursor = start
    remaining = budget
    while remaining > 0 and cursor < end:
        morning = datetime.combine(cursor.date(), time(7))
        night = datetime.combine(cursor.date(), time(23))
        cursor = max(cursor, morning)
        available = int((min(night, end) - cursor).total_seconds() // 60)
        minutes = min(50, available, remaining)
        if minutes >= min(5, remaining):
            until = cursor + timedelta(minutes=minutes)
            windows.append(Window(start=cursor, end=until))
            remaining -= minutes
            cursor = until + BREAK
        else:
            cursor = datetime.combine(cursor.date() + timedelta(days=1), time(7))
    if remaining:
        raise ValueError(
            f"Only {budget - remaining} study minutes fit before the interview with breaks, "
            "overnight sleep and a 15-minute buffer. Reduce your study hours or check the interview time."
        )
    return windows


def check_plan(draft, inputs, windows, links):
    if len(draft.blocks) != len(windows):
        raise ValueError("The plan needs one block per study window.")
    if sum(block.duration_minutes for block in draft.blocks) != inputs.budget:
        raise ValueError("The plan does not fit the study budget.")
    for block, window in zip(draft.blocks, windows):
        if block.duration_minutes != window.minutes:
            raise ValueError("The study block exceeds or falls short of its assigned window.")
        if block.reference is not None and block.reference not in links:
            raise ValueError("A study block links to an unknown lesson.")


def plan_request(profile, inputs, attempts, available_items):
    windows = build_windows(inputs.start, inputs.interview, inputs.budget)
    resources = {}
    for project in profile.projects[:5]:
        for section in SECTIONS:
            resources[f"project:{project.id}:{section}"] = f"{project.title} · {section}"
    for topic in topics(profile)[:25]:
        resources[f"skill:Basics:{topic}"] = f"{topic} · Basics"
    known_topics = set(topics(profile))
    for item in available_items:
        if item.kind == "skill" and item.slot.split(":", 2)[-1] in known_topics:
            resources[item.slot] = item.title

    links = {f"R{index}": title for index, title in enumerate(resources.values(), 1)}
    slots = dict(zip(links, resources))
    signals = []
    for attempt in attempts[:5]:
        signals.append({
            "focus": attempt.focus,
            "accuracy": attempt.feedback.accuracy.score,
            "coverage": attempt.feedback.coverage.score,
            "gap": attempt.feedback.missing[:300],
        })

    # Validate the provider's draft, then attach app-owned times and links before storage.
    def validate(draft):
        check_plan(draft, inputs, windows, slots)

    context = {
        "study_windows_minutes": [window.minutes for window in windows],
        "study_minutes": inputs.budget,
        "schedule": [[window.start.isoformat(), window.end.isoformat()] for window in windows],
        "interview": inputs.interview.isoformat(),
        "weak_areas": inputs.weak_areas,
        "role_context": inputs.role_context,
        "target": target_context(profile),
        "skills": topics(profile)[:35],
        "projects": [
            {"title": p.title, "summary": p.summary[:350], "technologies": p.technologies[:8]}
            for p in profile.projects[:5]
        ],
        "recent_practice": signals,
        "resources": links,
    }
    def with_schedule(draft):
        return Plan(inputs=inputs, windows=windows, blocks=draft.blocks, links=slots)

    return Request("plan", "plan", "Preparation plan", context, PlanDraft, validate, with_schedule)
