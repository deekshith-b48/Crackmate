"""Readiness (1-10), interview risk (0-10) and the study-first queue. Pure arithmetic over stored evidence: no model.

readiness  = how well you know it, from quiz accuracy, spaced-repetition retention and a small completion bonus.
likelihood = how likely an interviewer asks about it, from how many of your projects depend on it.
risk       = 10 x likelihood x (1 - strength). Unassessed topics are treated as 0.3 strong (unknown, not zero).
"""
import json
import math
from datetime import datetime, timezone

from core.career import graph as g
from core.interview import Interviews
from core.review import Reviews

UNASSESSED_STRENGTH = 0.3
SHRINK = 2  # retention counts as if SHRINK neutral cards were already reviewed, so one flashcard cannot define a topic
DIMS = ("accuracy", "coverage", "reasoning", "clarity")


def _evidence(core, record, topics):
    """{topic: [(time, score 0..1, independent)]} from practice attempts and interview answers."""
    out = {t: [] for t in topics}
    for a in core.store.attempts(record.id):
        topic = a.focus.split(" · ")[0]
        if topic in out:
            meta = a.feedback.learning_metadata or {}
            out[topic].append((a.created_at.replace(" ", "T"), sum(getattr(a.feedback, d).score for d in DIMS) / 16, meta.get("independent") is True))
    for s in Interviews(core.store).list(record.id):
        for t in s.turns:
            topic = t.topic or s.topic
            for fb in ([t.feedback] if t.feedback else []) + t.retries:
                if topic in out:
                    meta = fb.learning_metadata or {}
                    out[topic].append((meta.get("time") or "", sum(getattr(fb, d).score for d in DIMS) / 16, meta.get("independent") is True))
    return {k: sorted(v) for k, v in out.items()}


def _retention(core, record, topics):
    """{topic: [0..1 per card]}. A card counts fully once its interval reaches three weeks. A lapse counts 0,
    and a card with a single successful review is ignored: it has not had time to prove anything."""
    out = {t: [] for t in topics}
    for row in Reviews(core.store).all(record.id):
        parts = row["slot"].split(":", 2)
        if parts[0] == "skill" and parts[-1] in out:
            if row["reps"] != 1:
                out[parts[-1]].append(min(row["interval"] / 21, 1.0) if row["reps"] else 0.0)
    return out


def _completed(core, record):
    return {i.title.split(" · ")[0] for i in core.store.items(record.id) if i.kind == "skill" and core.store.completed(record.id, i)}


def compute(core, record, graph, now=None):
    now = now or datetime.now(timezone.utc)
    concepts = {n["label"]: n["id"] for n in graph["nodes"] if n["type"] == "concept"}
    ev, ret, done = _evidence(core, record, concepts), _retention(core, record, concepts), _completed(core, record)
    reach = g.reach(graph)
    prereq = g.adjacency(graph, "prerequisite")
    dependents = {}
    for source, targets in prereq.items():
        for t in targets:
            dependents[t] = dependents.get(t, 0) + 1
    rows = {}
    for topic, cid in concepts.items():
        answers = ev[topic][-5:]
        parts, why = [], []
        if answers:
            quiz = sum(s * (1.0 if ind else 0.8) for _, s, ind in answers) / len(answers)
            parts.append((0.6, quiz))
            why.append(f"Quiz accuracy {quiz * 100:.0f}% over your last {len(answers)} scored answer(s); hints or retries count 20% less.")
        if ret[topic]:
            retention = (sum(ret[topic]) + UNASSESSED_STRENGTH * SHRINK) / (len(ret[topic]) + SHRINK)
            parts.append((0.3, retention))
            why.append(f"Retention {retention * 100:.0f}% across {len(ret[topic])} review card(s); a few cards are needed before it moves far from neutral.")
        assessed = bool(parts)
        strength = None
        if assessed:
            weight = sum(w for w, _ in parts)
            strength = sum(w * v for w, v in parts) / weight
            if topic in done:
                strength = min(1.0, strength + 0.05)
                why.append("Lesson completed (small bonus).")
            last = ev[topic][-1][0] if ev[topic] else ""
            try:
                days = max(0, (now - datetime.fromisoformat(last.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)).days) if last else 0
            except ValueError:
                days = 0
            if days:
                strength = max(0.0, strength - 0.15 * min(days / 45, 1))
                why.append(f"{days} day(s) since your last scored answer lowers it slightly.")
        else:
            why.append("Not assessed yet. Practise a few questions to get a score.")
        projects = len(reach.get(cid, ()))
        likelihood = min(1.0, 0.3 + 0.2 * min(projects, 3) + 0.03 * min(dependents.get(cid, 0), 5))
        use = strength if assessed else UNASSESSED_STRENGTH
        trend = "flat"
        if len(ev[topic]) >= 2:
            delta = ev[topic][-1][1] - ev[topic][-2][1]
            trend = "up" if delta > 0.05 else "down" if delta < -0.05 else "flat"
        rows[topic] = {"topic": topic, "assessed": assessed, "readiness": round(1 + 9 * strength, 1) if assessed else None,
                       "likelihood": round(likelihood, 2), "risk": round(10 * likelihood * (1 - use), 1), "trend": trend,
                       "projects": projects, "dependents": dependents.get(cid, 0), "why": why + [f"Used by {projects} of your project(s); {dependents.get(cid, 0)} other topic(s) build on it."]}
    assessed = [r for r in rows.values() if r["assessed"]]
    overall = round(sum(r["readiness"] * r["likelihood"] for r in assessed) / sum(r["likelihood"] for r in assessed), 1) if assessed else None
    return {"overall": overall, "assessed": len(assessed), "total": len(rows), "topics": sorted(rows.values(), key=lambda r: (-r["risk"], r["topic"]))}


def study_first(signals, limit=5):
    return [{"topic": r["topic"], "risk": r["risk"], "assessed": r["assessed"], "readiness": r["readiness"],
             "reason": f"Risk {r['risk']}/10: " + ("not assessed yet" if not r["assessed"] else f"readiness {r['readiness']}/10") + f", used by {r['projects']} project(s)."}
            for r in signals["topics"][:limit] if r["risk"] > 0]


def question_count(core, record, topics):
    """How many saved lesson questions cover these topics (used for 'blast radius' wording)."""
    total = 0
    for item in core.store.items(record.id):
        if item.kind == "skill" and item.title.split(" · ")[0] in topics:
            body = json.loads(item.body)
            total += len(body.get("questions", [])) + len(body.get("follow_ups", []))
    return total
