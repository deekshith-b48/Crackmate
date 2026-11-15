"""The Home dashboard: readiness, what to study next, and what is due."""
from core.learning import Learning, readiness, utcnow
from core.review import Reviews


def build(core, record):
    learning = Learning(core.store, record.id)
    learning.sync()
    now = utcnow()
    progress = learning.progress(now)
    overall, assessed, total, scores = readiness(progress)
    settings = learning.settings()
    lessons = [i for i in core.store.items(record.id) if i.kind in ("project", "skill")]
    weakest = sorted(({"name": t["name"], "score": scores[t["id"]]} for t in progress if scores[t["id"]] is not None),
                     key=lambda row: row["score"])[:3]
    return {
        "readiness": {"overall": overall, "assessed": assessed, "total": total},
        "weakest": weakest,
        "queue": learning.queue(now, settings["daily_minutes"])[:3],
        "due_reviews": len(Reviews(core.store).due(record.id)),
        "lessons": {"saved": len(lessons), "completed": sum(core.store.completed(record.id, i) for i in lessons)},
        "attempts": len(core.store.attempts(record.id)),
        "interview": settings.get("interview") or None,
        "projects": len(record.profile.projects),
    }
