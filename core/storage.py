"""Local profile storage. Each write runs in a short transaction."""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from uuid import uuid4

from core.schemas import Feedback, Profile


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProfileRecord:
    id: str
    revision: int
    profile: Profile


@dataclass(frozen=True)
class Item:
    slot: str
    kind: str
    title: str
    digest: str
    model: str
    revision: int
    body: str


@dataclass(frozen=True)
class Attempt:
    id: str
    focus: str
    question: str
    answer: str
    feedback: Feedback
    created_at: str


class Storage:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS items (
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    slot TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, digest TEXT NOT NULL,
                    model TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY (profile_id, slot)
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    id TEXT NOT NULL, focus TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL,
                    feedback TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (profile_id, id)
                );
                CREATE TABLE IF NOT EXISTS progress (
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    slot TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY (profile_id, slot)
                );
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA secure_delete = ON")
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _profile(row):
        return ProfileRecord(row["id"], row["revision"], Profile.model_validate_json(row["body"]))

    def profiles(self):
        with self.connect() as connection:
            return [self._profile(row) for row in connection.execute("SELECT * FROM profiles ORDER BY rowid DESC")]

    def get(self, profile_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return self._profile(row) if row else None

    def create(self, profile: Profile):
        record = ProfileRecord(uuid4().hex, 1, profile)
        with self.connect() as connection:
            connection.execute("INSERT INTO profiles VALUES (?, ?, ?)", (record.id, 1, profile.model_dump_json()))
        return record

    def save(self, record: ProfileRecord, profile: Profile):
        if profile == record.profile:
            return record
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE profiles SET revision = revision + 1, body = ? WHERE id = ? AND revision = ?",
                (profile.model_dump_json(), record.id, record.revision),
            )
            if cursor.rowcount == 0:
                raise StorageError("This profile changed in another tab. Reload it and apply your edits again.")
        return ProfileRecord(record.id, record.revision + 1, profile)

    def delete(self, profile_id):
        with self.connect() as connection:
            connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))

    def _items(self, profile_id, slot=None):
        query = "SELECT slot, kind, title, digest, model, revision, body FROM items WHERE profile_id = ?"
        params = (profile_id,)
        if slot is not None:
            query += " AND slot = ?"
            params += (slot,)
        with self.connect() as connection:
            return [Item(**row) for row in connection.execute(query + " ORDER BY rowid DESC", params)]

    def items(self, profile_id):
        return self._items(profile_id)

    def item(self, profile_id, slot):
        return next(iter(self._items(profile_id, slot)), None)

    def assert_current(self, connection, record):
        row = connection.execute("SELECT revision FROM profiles WHERE id = ?", (record.id,)).fetchone()
        if row is None or row["revision"] != record.revision:
            raise StorageError("The profile changed while you worked. Reload and retry with the latest profile.")

    def save_item(self, record, item):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.assert_current(connection, record)
            connection.execute("""
                INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, slot) DO UPDATE SET
                    title=excluded.title, digest=excluded.digest, model=excluded.model,
                    revision=excluded.revision, body=excluded.body
            """, (record.id, item.slot, item.kind, item.title, item.digest, item.model, item.revision, item.body))
            connection.execute("DELETE FROM progress WHERE profile_id=? AND slot=?", (record.id, item.slot))

    def completed(self, profile_id, item):
        with self.connect() as connection:
            return connection.execute(
                "SELECT 1 FROM progress WHERE profile_id=? AND slot=? AND digest=?",
                (profile_id, item.slot, item.digest),
            ).fetchone() is not None

    def mark_completed(self, record, item, completed):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.assert_current(connection, record)
            current = connection.execute(
                "SELECT digest, body FROM items WHERE profile_id=? AND slot=?", (record.id, item.slot)
            ).fetchone()
            if current is None or (current["digest"], current["body"]) != (item.digest, item.body):
                raise StorageError("This lesson changed. Reload before updating progress.")
            if completed:
                connection.execute("INSERT OR REPLACE INTO progress VALUES (?, ?, ?)", (record.id, item.slot, item.digest))
            else:
                connection.execute("DELETE FROM progress WHERE profile_id=? AND slot=?", (record.id, item.slot))

    def attempts(self, profile_id):
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT id, focus, question, answer, feedback, created_at
                FROM attempts WHERE profile_id=? ORDER BY rowid DESC
            """, (profile_id,)).fetchall()
        return [
            Attempt(**(dict(row) | {"feedback": Feedback.model_validate_json(row["feedback"])}))
            for row in rows
        ]

    def save_attempt(self, record, attempt_id, focus, question, answer, feedback):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.assert_current(connection, record)
            connection.execute("""
                INSERT INTO attempts (profile_id, id, focus, question, answer, feedback)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(profile_id, id) DO NOTHING
            """, (record.id, attempt_id, focus, question, answer, feedback.model_dump_json()))
