"""Question-level spaced repetition (SM-2). Local SQLite only."""
from datetime import date, timedelta
import hashlib

GRADES = {"Again": 1, "Hard": 3, "Good": 4, "Easy": 5}


def sm2(ease, interval, reps, quality):
    """Return (ease, interval_days, reps). Quality below 3 restarts and is due today."""
    if quality < 3:
        return ease, 0, 0
    interval = 1 if reps == 0 else 6 if reps == 1 else max(1, round(interval * ease))
    ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return ease, interval, reps + 1


def question_id(slot, question):
    return hashlib.sha256(f"{slot}\n{question}".encode()).hexdigest()[:16]


class Reviews:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    qid TEXT NOT NULL, slot TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL,
                    hint TEXT NOT NULL, ease REAL NOT NULL, interval INTEGER NOT NULL,
                    reps INTEGER NOT NULL, due TEXT NOT NULL, PRIMARY KEY (profile_id, qid)
                )""")

    def rate(self, profile_id, slot, question, answer, hint, grade, today=None):
        today = today or date.today()
        qid = question_id(slot, question)
        with self.store.connect() as db:
            row = db.execute("SELECT ease, interval, reps FROM reviews WHERE profile_id=? AND qid=?",
                             (profile_id, qid)).fetchone()
            ease, interval, reps = sm2(*(tuple(row) if row else (2.5, 0, 0)), GRADES[grade])
            db.execute("INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?)", (
                profile_id, qid, slot, question, answer, hint, ease, interval, reps,
                (today + timedelta(days=interval)).isoformat()))
        return interval

    def all(self, profile_id):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute("SELECT slot, interval, reps FROM reviews WHERE profile_id=?", (profile_id,))]

    def due(self, profile_id, today=None):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM reviews WHERE profile_id=? AND due<=? ORDER BY due, rowid",
                (profile_id, (today or date.today()).isoformat()))]


class ClaimTicks:
    """Which claims the user said they can defend, per claim-check version."""

    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS claim_ticks (
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    digest TEXT NOT NULL, idx INTEGER NOT NULL, PRIMARY KEY (profile_id, digest, idx)
                )""")

    def get(self, profile_id, digest):
        with self.store.connect() as db:
            return {r[0] for r in db.execute(
                "SELECT idx FROM claim_ticks WHERE profile_id=? AND digest=?", (profile_id, digest))}

    def set(self, profile_id, digest, idx, on):
        with self.store.connect() as db:
            if on:
                db.execute("INSERT OR IGNORE INTO claim_ticks VALUES (?,?,?)", (profile_id, digest, idx))
            else:
                db.execute("DELETE FROM claim_ticks WHERE profile_id=? AND digest=? AND idx=?",
                           (profile_id, digest, idx))
