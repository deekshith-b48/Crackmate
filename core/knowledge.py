"""Shared personal library with transactional versions and bounded lexical retrieval."""
import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4


def chunks(text, limit=1600):
    heading = ""
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        if paragraph.startswith("#"):
            heading = paragraph.splitlines()[0].lstrip("# ")
        for start in range(0, len(paragraph), limit):
            yield heading, paragraph[start:start + limit]


class Library:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS library_sources(
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, location TEXT UNIQUE NOT NULL,
                    kind TEXT NOT NULL, hash TEXT NOT NULL, retrieved TEXT NOT NULL,
                    license TEXT NOT NULL, status TEXT NOT NULL, error TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS library_versions(
                    source TEXT REFERENCES library_sources(id) ON DELETE CASCADE,
                    hash TEXT, text TEXT NOT NULL, retrieved TEXT NOT NULL,
                    PRIMARY KEY(source,hash)
                );
                CREATE TABLE IF NOT EXISTS library_passages(
                    id TEXT PRIMARY KEY, source TEXT REFERENCES library_sources(id) ON DELETE CASCADE,
                    hash TEXT NOT NULL, heading TEXT NOT NULL, position INTEGER NOT NULL, text TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS library_metadata(key TEXT PRIMARY KEY,value TEXT);
                INSERT OR IGNORE INTO library_metadata VALUES('schema','1');
            """)
            try:
                db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS library_fts USING fts5(id UNINDEXED,text)")
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False

    def sources(self):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM library_sources ORDER BY title")]

    def import_text(self, title, location, text, kind="text", license="Unknown", bulk=False):
        text = text.strip()
        if not text or len(text) > 100000:
            raise ValueError("Provide between 1 and 100,000 characters.")
        digest = hashlib.sha256(text.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM library_sources WHERE location=?", (location,)).fetchone()
            # Bulk repo imports and your own sources are capped separately.
            scope = "= 'repo'" if bulk else "!= 'repo'"
            count = db.execute(f"SELECT count(*) FROM library_sources WHERE kind {scope}").fetchone()[0]
            size = db.execute(f"SELECT coalesce(sum(length(v.text)),0) FROM library_versions v "
                              f"JOIN library_sources s ON s.id=v.source WHERE s.kind {scope}").fetchone()[0]
            max_sources, max_chars = (1000, 25_000_000) if bulk else (100, 5_000_000)
            if (not old and count >= max_sources) or size + len(text) > max_chars:
                raise ValueError(f"Library limit reached. Delete unused sources ({max_sources} sources / {max_chars:,} characters).")
            ident = old["id"] if old else uuid4().hex
            if old and old["hash"] == digest:
                db.execute("UPDATE library_sources SET retrieved=?,status='ready',error='' WHERE id=?", (now,ident))
                return "Unchanged"
            if self.fts:
                db.execute("DELETE FROM library_fts WHERE id IN (SELECT id FROM library_passages WHERE source=?)", (ident,))
            db.execute("DELETE FROM library_passages WHERE source=?", (ident,))
            db.execute("""INSERT INTO library_sources VALUES(?,?,?,?,?,?,?,'ready','')
                ON CONFLICT(id) DO UPDATE SET title=excluded.title,hash=excluded.hash,
                retrieved=excluded.retrieved,status='ready',error=''""", (ident,title,location,kind,digest,now,license))
            db.execute("INSERT OR IGNORE INTO library_versions VALUES(?,?,?,?)",(ident,digest,text,now))
            for position,(heading,body) in enumerate(chunks(text)):
                passage = f"{ident[:12]}-{digest[:12]}-{position}"
                db.execute("INSERT INTO library_passages VALUES(?,?,?,?,?,?)",(passage,ident,digest,heading,position,body))
                if self.fts:
                    db.execute("INSERT INTO library_fts VALUES(?,?)",(passage,body))
        return "Imported"

    def failed(self, ident, message):
        with self.store.connect() as db:
            db.execute("UPDATE library_sources SET status='refresh failed',error=? WHERE id=?",(message,ident))

    def delete(self, ident):
        with self.store.connect() as db:
            if self.fts:
                db.execute("DELETE FROM library_fts WHERE id IN (SELECT id FROM library_passages WHERE source=?)",(ident,))
            db.execute("DELETE FROM library_sources WHERE id=?",(ident,))

    def search(self, query):
        words = list(dict.fromkeys(re.findall(r"\w{3,}",query.lower())))[:20]
        if not words:
            return []
        with self.store.connect() as db:
            if self.fts:
                rows = db.execute("""SELECT p.*,s.title,s.location,s.retrieved,s.license
                    FROM library_fts f JOIN library_passages p ON p.id=f.id
                    JOIN library_sources s ON s.id=p.source WHERE library_fts MATCH ?
                    ORDER BY bm25(library_fts) LIMIT 30""",(" OR ".join('"'+w+'"' for w in words),)).fetchall()
            else:
                rows = db.execute("""SELECT p.*,s.title,s.location,s.retrieved,s.license
                    FROM library_passages p JOIN library_sources s ON s.id=p.source""").fetchall()
                rows = sorted(rows,key=lambda row: -sum(row["text"].lower().count(w) for w in words))
                rows = [r for r in rows if any(w in r["text"].lower() for w in words)]
        found, seen = [], set()
        for row in rows:
            body_hash = hashlib.sha256(row["text"].encode()).hexdigest()
            if row["source"] in seen or body_hash in seen:
                continue
            found.append(dict(row))
            seen.update((row["source"],body_hash))
            if len(found) == 4:
                break
        return found
