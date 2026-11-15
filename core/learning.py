"""Deterministic learning evidence, revision and planning. No hosted calls."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import json
from uuid import uuid4

from core.material import CORE_TOPICS

DIMENSIONS = ("accuracy", "coverage", "reasoning", "clarity")
RUBRIC = "technical-0-4-v1"
DEFAULTS = {
    "timezone": "Asia/Kolkata", "threshold": 3, "successes": 2,
    "intervals": [1, 3, 7, 14], "daily_minutes": 60, "session_minutes": 25,
    "unavailable": [], "interview": "", "priorities": [],
}


def utcnow():
    return datetime.now(timezone.utc)


def topic_id(name):
    return hashlib.sha256(name.casefold().strip().encode()).hexdigest()[:16]


def validate_catalogue(topics):
    lookup = {t["id"]: t for t in topics}
    if len(lookup) != len(topics):
        raise ValueError("Topic identifiers must be unique.")
    visited, active = set(), set()
    def visit(ident):
        if ident not in lookup:
            raise ValueError("A prerequisite topic does not exist.")
        if ident in active:
            raise ValueError("Prerequisites cannot form a cycle.")
        if ident in visited:
            return
        active.add(ident)
        for prerequisite in lookup[ident]["prerequisites"]:
            visit(prerequisite)
        active.remove(ident)
        visited.add(ident)
    for ident in lookup:
        visit(ident)


def readiness(progress, recent=3):
    """Coaching estimate, 0-100, from each topic's latest compatible answers.

    Answers given with a hint, a reveal or a retry (or with unknown history) cap a topic at 70.
    Overall averages assessed topics only, so it also reports how many topics that is.
    Returns (overall or None, assessed_count, total_count, {topic_id: score or None}).
    """
    scores = {}
    for topic in progress:
        usable = [e for e in topic["evidence"] if e["rubric"] == RUBRIC and e["time"]][-recent:]
        if not usable:
            scores[topic["id"]] = None
            continue
        value = sum(sum(e["scores"].values()) / (4 * len(e["scores"])) for e in usable) / len(usable) * 100
        independent = usable[-1]["independent"] is True
        scores[topic["id"]] = round(value if independent else min(value, 70))
    assessed = [v for v in scores.values() if v is not None]
    return (round(sum(assessed) / len(assessed)) if assessed else None), len(assessed), len(scores), scores


class Learning:
    def __init__(self, store, profile_id):
        self.store, self.profile_id = store, profile_id
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS learning_topics(
                    profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                    id TEXT, body TEXT NOT NULL, PRIMARY KEY(profile_id,id));
                CREATE TABLE IF NOT EXISTS learning_evidence(
                    profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                    id TEXT, body TEXT NOT NULL, PRIMARY KEY(profile_id,id));
                CREATE TABLE IF NOT EXISTS learning_preferences(
                    profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                    id TEXT, body TEXT NOT NULL, PRIMARY KEY(profile_id,id));
                CREATE TABLE IF NOT EXISTS learning_plans(
                    profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                    id TEXT, body TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(profile_id,id));
                CREATE TABLE IF NOT EXISTS learning_reviews(
                    profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                    topic TEXT, evidence_id TEXT, due TEXT NOT NULL,
                    PRIMARY KEY(profile_id,topic,evidence_id));
            """)
            for name in CORE_TOPICS:
                prerequisites = []
                if name == "System design fundamentals":
                    prerequisites = [topic_id("Networking"), topic_id("Database fundamentals")]
                if name == "Cloud and deployment fundamentals":
                    prerequisites = [topic_id("Networking")]
                body = dict(id=topic_id(name),name=name,description="Interview fundamentals and practical examples.",
                            category="Core",prerequisites=prerequisites,skills=[name],
                            levels=["Basics","Intermediate","Advanced"],role="")
                db.execute("INSERT OR IGNORE INTO learning_topics VALUES(?,?,?)",(profile_id,body["id"],json.dumps(body)))

    def rows(self, table):
        allowed = {"learning_topics","learning_evidence","learning_preferences","learning_plans"}
        if table not in allowed:
            raise ValueError("Unknown learning data.")
        with self.store.connect() as db:
            return [json.loads(r[0]) for r in db.execute(f"SELECT body FROM {table} WHERE profile_id=?",(self.profile_id,))]

    def topics(self):
        return sorted(self.rows("learning_topics"),key=lambda t:t["name"])

    def preferences(self):
        return {p["id"]:p["value"] for p in self.rows("learning_preferences")}

    def settings(self):
        return DEFAULTS | self.preferences().get("settings",{})

    def preference(self, ident, value):
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO learning_preferences VALUES(?,?,?)",
                       (self.profile_id,ident,json.dumps({"id":ident,"value":value})))

    def save_topic(self, topic):
        if not topic["name"].strip():
            raise ValueError("A topic needs a name.")
        catalogue = [t for t in self.topics() if t["id"]!=topic["id"]] + [topic]
        validate_catalogue(catalogue)
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO learning_topics VALUES(?,?,?)",
                       (self.profile_id,topic["id"],json.dumps(topic)))

    def mappings(self, label):
        explicit = self.preferences().get("mapping:"+label)
        if explicit is not None:
            return explicit
        normalized = label.casefold().split(" · ")[0]
        return [t["id"] for t in self.topics() if normalized in [t["name"].casefold(),*[s.casefold() for s in t["skills"]]]]

    def evidence(self):
        return sorted(self.rows("learning_evidence"),key=lambda e:(e["time"] or "",e["id"]))

    def ingest(self, ident, label, question, feedback, *, at=None, metadata=None, source="text practice"):
        metadata = metadata or {}
        evidence = {
            "id":ident,"label":label,"question":question,
            "topics":self.mappings(label),"time":at,
            "rubric":metadata.get("rubric","unknown"),
            "difficulty":metadata.get("difficulty","unknown"),
            "hint":metadata.get("hint"),"revealed":metadata.get("revealed"),
            "retry":metadata.get("retry"),"independent":metadata.get("independent"),
            "source":source,"scores":{d:getattr(feedback,d).score for d in DIMENSIONS},
            "correct":feedback.correct,"missing":feedback.missing,
            "uncertainty":"Coaching estimates. Citation checks establish passage identity only.",
        }
        with self.store.connect() as db:
            db.execute("INSERT OR IGNORE INTO learning_evidence VALUES(?,?,?)",(self.profile_id,ident,json.dumps(evidence)))

    def sync(self):
        # Backfill per profile only. Historical metadata remains unknown.
        attempts = self.store.attempts(self.profile_id)
        valid = {"text:"+a.id for a in attempts}
        for attempt in attempts:
            self.ingest("text:"+attempt.id,attempt.focus,attempt.question,attempt.feedback,
                        at=attempt.created_at.replace(" ","T")+"+00:00", metadata=attempt.feedback.learning_metadata)
        with self.store.connect() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='interviews'").fetchone()
        if exists:
            from core.interview import Interviews
            for session in Interviews(self.store).list(self.profile_id):
                for turn in session.turns:
                    for index,feedback in enumerate(turn.retries + ([turn.feedback] if turn.feedback else [])):
                        ident=f"interview:{session.id}:{turn.id}:{index}"
                        valid.add(ident)
                        self.ingest(ident,turn.topic or session.topic,turn.question.question,feedback,source=session.mode,
                                    at=feedback.learning_metadata.get("time"),
                                    metadata=feedback.learning_metadata or {"retry":index>0})
        with self.store.connect() as db:
            for evidence in self.evidence():
                if evidence["id"] not in valid and not evidence["id"].startswith("diagnostic:"):
                    db.execute("DELETE FROM learning_evidence WHERE profile_id=? AND id=?",(self.profile_id,evidence["id"]))

    def progress(self, now):
        settings=self.settings()
        zone=ZoneInfo(settings["timezone"])
        today=now.astimezone(zone).date()
        preferences=self.preferences()
        evidence=self.evidence()
        completed={i.title.split(" · ")[0] for i in self.store.items(self.profile_id) if self.store.completed(self.profile_id,i)}
        result=[]
        schedule=[]
        for topic in self.topics():
            cutoff=preferences.get("reset:"+topic["id"],"")
            rows=[e for e in evidence if topic["id"] in e["topics"] and (not cutoff or (e["time"] or "")>cutoff)]
            usable=[e for e in rows if e["rubric"]==RUBRIC and e["time"]]
            successes=0
            due=None
            strong=[]
            for e in usable:
                independent=e["independent"] is True and e["hint"] is False and e["revealed"] is False and e["retry"] is False
                passed=min(e["scores"].values())>=settings["threshold"]
                if independent and passed:
                    successes+=1
                    strong.append(e["question"])
                else:
                    successes=0
                    strong=[]
                interval=settings["intervals"][min(max(successes-1,0),len(settings["intervals"])-1)] if independent and passed else 1
                due=datetime.fromisoformat(e["time"]).astimezone(zone).date()+timedelta(days=interval)
                schedule.append((topic["id"],e["id"],due.isoformat()))
            state="Learning" if rows or topic["name"] in completed else "Not assessed"
            if usable:
                last=usable[-1]
                if min(last["scores"].values())<settings["threshold"]:
                    state="Needs revision"
                elif len(set(strong))>=settings["successes"]:
                    state="Demonstrated recently"
                if due and due<=today:
                    state="Due for review"
            override=preferences.get("due:"+topic["id"])
            if override:
                due=datetime.fromisoformat(override).date()
                if due<=today:
                    state="Due for review"
            result.append(topic | {"state":state,"due":due.isoformat() if due else None,"evidence":rows,
                                   "count":len(usable),"limitation":"Single or assisted answers and unknown rubrics do not establish understanding."})
        with self.store.connect() as db:
            db.execute("DELETE FROM learning_reviews WHERE profile_id=?",(self.profile_id,))
            db.executemany("INSERT INTO learning_reviews VALUES(?,?,?,?)",
                           [(self.profile_id,*row) for row in schedule])
        return result

    def queue(self, now, minutes):
        progress=self.progress(now)
        by_id={t["id"]:t for t in progress}
        preferences=self.preferences()
        settings=self.settings()
        relevance=set()
        profile=self.store.get(self.profile_id).profile
        for group in profile.skills.model_dump().values():
            for skill in group:
                relevance.update(self.mappings(skill))
        items=[]
        for topic in progress:
            choice=preferences.get("queue:"+topic["id"],{})
            if choice.get("dismissed") or choice.get("postpone","")>now.astimezone(ZoneInfo(settings["timezone"])).date().isoformat():
                continue
            score={"Due for review":90,"Needs revision":80,"Not assessed":40,"Learning":50,"Demonstrated recently":10}[topic["state"]]
            reason=topic["state"]
            gaps=[by_id[p]["name"] for p in topic["prerequisites"] if by_id[p]["state"]!="Demonstrated recently"]
            if gaps:
                reason+="; first review "+", ".join(gaps)
                score-=15
            needed = any(topic["id"] in other["prerequisites"] and other["state"] != "Demonstrated recently" for other in progress)
            if needed and topic["state"] != "Demonstrated recently":
                score+=15
                reason+="; prerequisite gap"
            if settings["interview"]:
                days=(datetime.fromisoformat(settings["interview"]).date()-now.astimezone(ZoneInfo(settings["timezone"])).date()).days
                if 0<=days<=2 and topic["state"] in ("Needs revision", "Due for review"):
                    score+=30
                    reason+="; interview within two calendar days"
            if topic["id"] in relevance:
                score+=10
                reason+="; resume skill"
            if topic["id"] in settings["priorities"]:
                score+=20
                reason+="; selected priority"
            if choice.get("pinned"):
                score+=100
                reason+="; pinned"
            activity="Answer a different independent question" if topic["count"] else "Review prerequisites, then answer a question"
            if topic["state"]=="Needs revision":
                activity="Study a simpler worked example before a different question"
            items.append({"topic":topic["id"],"name":topic["name"],"reason":reason,"score":score,
                          "duration":min(settings["session_minutes"],minutes),"activity":activity})
        items.sort(key=lambda i:(-i["score"],i["name"]))
        selected=[]
        remaining=minutes
        for item in items:
            if remaining<5:
                break
            item["duration"]=min(item["duration"],remaining)
            selected.append(item)
            remaining-=item["duration"]+5
        return selected

    def propose(self, now, days=7):
        settings=self.settings()
        zone=ZoneInfo(settings["timezone"])
        today=now.astimezone(zone).date()
        interview=datetime.fromisoformat(settings["interview"]).date() if settings["interview"] else None
        if interview and interview<today:
            raise ValueError("The interview date has passed. Update or clear it to propose a plan.")
        previous=self.active_plan()
        preserved=[b for b in previous.get("blocks",[]) if b["completed"] or b["pinned"]]
        blocks=list(preserved)
        for offset in range(days):
            day=today+timedelta(days=offset)
            if interview and day>interview:
                break
            if day.isoformat() in settings["unavailable"]:
                continue
            remaining=settings["daily_minutes"]-sum(b["duration"] for b in blocks if b["date"]==day.isoformat())
            if remaining<0:
                raise ValueError("Pinned or completed blocks exceed the new daily budget. Adjust the budget first.")
            for item in self.queue(now,remaining):
                blocks.append(item | {"id":uuid4().hex,"date":day.isoformat(),"completed":False,"pinned":False,
                                       "outcome":"Explain one worked example and attempt one question without hints."})
        return {"id":uuid4().hex,"created":now.isoformat(),"blocks":blocks,
                "reason":"Rebuilt from current evidence, due reviews, priorities and available study minutes.",
                "base":previous.get("id"),"settings":settings}

    def active_plan(self):
        with self.store.connect() as db:
            row=db.execute("SELECT body FROM learning_plans WHERE profile_id=? AND active=1",(self.profile_id,)).fetchone()
        return json.loads(row[0]) if row else {}

    def apply_plan(self, plan):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current=db.execute("SELECT id FROM learning_plans WHERE profile_id=? AND active=1",(self.profile_id,)).fetchone()
            if (current[0] if current else None)!=plan["base"]:
                raise ValueError("The active plan changed. Propose it again.")
            db.execute("UPDATE learning_plans SET active=0 WHERE profile_id=?",(self.profile_id,))
            db.execute("INSERT INTO learning_plans VALUES(?,?,?,1)",(self.profile_id,plan["id"],json.dumps(plan)))

    def update_block(self, ident, field, value):
        if field not in ("completed","pinned"):
            raise ValueError("Invalid activity change.")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT body FROM learning_plans WHERE profile_id=? AND active=1",(self.profile_id,)).fetchone()
            if not row:
                raise ValueError("Apply a plan first.")
            plan=json.loads(row[0])
            for block in plan["blocks"]:
                if block["id"]==ident:
                    block[field]=bool(value)
            db.execute("UPDATE learning_plans SET body=? WHERE profile_id=? AND active=1",(json.dumps(plan),self.profile_id))

    def remap(self, label, topics):
        if not set(topics)<= {t["id"] for t in self.topics()}:
            raise ValueError("Choose existing topics.")
        self.preference("mapping:"+label,topics)
        with self.store.connect() as db:
            for evidence in self.evidence():
                if evidence["label"]==label:
                    evidence["topics"]=topics
                    db.execute("UPDATE learning_evidence SET body=? WHERE profile_id=? AND id=?",
                               (json.dumps(evidence),self.profile_id,evidence["id"]))


def export_progress(learning, now):
    lines=["# Learning progress",f"Report generated {now.isoformat()}",
           "Coaching evidence only. Historical records may lack time, assistance and rubric metadata."]
    progress=learning.progress(now)
    overall,assessed,total,scores=readiness(progress)
    lines.append(f"Readiness · {'not assessed yet' if overall is None else f'{overall}/100'} · {assessed} of {total} topics assessed")
    for topic in progress:
        rows=topic["evidence"]
        dates=[e["time"] for e in rows if e["time"]]
        lines.extend([f"## {topic['name']}",f"{topic['state']} · {topic['count']} compatible scored attempts",
                      f"Review due {topic['due'] or 'not scheduled'}",
                      f"Evidence dates {min(dates) if dates else 'unknown'} to {max(dates) if dates else 'unknown'}"])
        for evidence in rows:
            lines.append(f"- {evidence['source']} · {evidence['question']} · rubric {evidence['rubric']} · scores {evidence['scores']}")
    lines.append("## Study next")
    for item in learning.queue(now,learning.settings()["daily_minutes"]):
        lines.append(f"- {item['name']} · {item['duration']} min · {item['activity']} · {item['reason']}")
    lines.append("## Active plan")
    for block in learning.active_plan().get("blocks",[]):
        lines.append(f"- {block['date']} · {block['name']} · {block['duration']} min · completed {block['completed']}")
    return "\n\n".join(lines)
