"""Shared lesson cache: generic lessons (no personal data) reused by every profile and user."""
from datetime import datetime, timezone


class SharedCache:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS shared_lessons(
                digest TEXT PRIMARY KEY, title TEXT NOT NULL, model TEXT NOT NULL,
                body TEXT NOT NULL, created TEXT NOT NULL)""")

    def get(self, digest):
        with self.store.connect() as db:
            row = db.execute("SELECT body FROM shared_lessons WHERE digest=?", (digest,)).fetchone()
        return row[0] if row else None

    def put(self, digest, title, model, body):
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO shared_lessons VALUES(?,?,?,?,?)",
                       (digest, title, model, body, datetime.now(timezone.utc).isoformat()))

    def count(self):
        with self.store.connect() as db:
            return db.execute("SELECT count(*) FROM shared_lessons").fetchone()[0]
