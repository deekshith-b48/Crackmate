"""A private, per-profile search index over your resume, your repositories and your saved lessons.

Each source carries a fingerprint (resume revision, repo commit, lesson digests). Only a source whose
fingerprint changed is re-read, so asking a question never re-indexes everything.
"""
import hashlib
import re
from pathlib import Path

from core.career import facts as facts_mod
from core.career import repo as repo_mod
from core.knowledge import chunks

MAX_FILE_CHARS, MAX_TOTAL = 60_000, 5_000_000
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "go.sum"}


def words(query):
    return list(dict.fromkeys(re.findall(r"\w{3,}", query.lower())))[:20]


class AskIndex:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS ask_fts USING fts5(
                    profile_id UNINDEXED, source UNINDEXED, kind UNINDEXED, title UNINDEXED, location UNINDEXED, text);
                CREATE TABLE IF NOT EXISTS ask_meta(
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    source TEXT NOT NULL, hash TEXT NOT NULL, PRIMARY KEY (profile_id, source));
            """)

    # ---- what to index
    @staticmethod
    def _profile(profile):
        def row(title, text):
            return {"kind": "resume", "title": title, "location": "Your resume", "text": text}
        if profile.summary:
            yield row("Summary", profile.summary)
        for entry in profile.work_experience:
            yield row("Work experience", entry)
        for entry in profile.education:
            yield row("Education", entry)
        skills = "; ".join(f"{k.replace('_', ' ')}: {', '.join(v)}" for k, v in profile.skills.model_dump().items() if v)
        if skills:
            yield row("Skills", skills)
        for p in profile.projects:
            parts = [p.summary, "Technologies: " + ", ".join(p.technologies) if p.technologies else "", "What I built: " + p.contribution if p.contribution else "",
                     p.implementation, *[f"{k}: {v}" for k, v in p.clarification.items()]]
            yield row(f"Project · {p.title}", "\n".join(x for x in parts if x))

    @staticmethod
    def _repo(project, repo):
        base = repo["url"]
        facts = repo["facts"]
        own = repo["ownership"]
        summary = (f"Detected stack: {', '.join(t['name'] for t in facts['technologies'][:14])}. {facts['loc']} lines of {', '.join(list(facts['languages'])[:3])}. "
                   f"Most-changed files: {', '.join(h['path'] for h in repo['hotspots'][:5]) or 'none yet'}."
                   + (f" The candidate wrote about {round(own['share'] * 100)}% of the added lines." if own["identified"] else ""))
        yield {"kind": "repo", "title": f"{project.title} · code facts", "location": base, "text": summary}
        root = repo_mod.REPOS / repo["_profile"] / project.id
        if not root.is_dir():
            return
        total = 0
        for path, text in facts_mod.read_repo(root).items():
            name = Path(path).name
            if name in SKIP_NAMES or path.endswith((".min.js", ".map", ".lock")) or total > MAX_TOTAL:
                continue
            text = text[:MAX_FILE_CHARS]
            total += len(text)
            for heading, body in chunks(text):
                if len(body.strip()) >= 40:
                    yield {"kind": "repo", "title": f"{project.title} · {path}" + (f" · {heading}" if heading else ""),
                           "location": f"{base}/blob/HEAD/{path}", "text": body}

    @staticmethod
    def _lessons(items):
        import json
        for item in items:
            body = json.loads(item.body)
            text = "\n".join(filter(None, [body.get("explanation", ""), body.get("example", ""), body.get("project_application", "")]))
            qa = "\n".join(f"Q: {q['question']}\nA: {q['answer']}" for q in body.get("questions", []))
            for part in (text, qa):
                for heading, chunk in chunks(part):
                    if len(chunk.strip()) >= 40:
                        yield {"kind": "lesson", "title": f"Your lesson · {item.title}", "location": "Saved lesson", "text": chunk}

    def sources(self, core, record):
        """[(source key, fingerprint, passage generator)]"""
        out = [("profile", hashlib.sha256(record.profile.model_dump_json().encode()).hexdigest()[:16], lambda: self._profile(record.profile))]
        for repo in repo_mod.Repos(self.store).all(record.id):
            project = next((p for p in record.profile.projects if p.id == repo["project_id"]), None)
            if project:
                repo = {**repo, "_profile": record.id}
                out.append((f"repo:{project.id}", repo["input_hash"] + str(repo["ownership"]["identified"]), lambda p=project, r=repo: self._repo(p, r)))
        lessons = [i for i in self.store.items(record.id) if i.kind in ("project", "skill")]
        out.append(("lessons", hashlib.sha256("".join(sorted(i.digest for i in lessons)).encode()).hexdigest()[:16], lambda: self._lessons(lessons)))
        return out

    # ---- keep it fresh
    def refresh(self, core, record):
        """Re-read only sources whose fingerprint changed. Returns the list of source keys that were rebuilt."""
        wanted = self.sources(core, record)
        changed = []
        with self.store.connect() as db:
            have = {r["source"]: r["hash"] for r in db.execute("SELECT source, hash FROM ask_meta WHERE profile_id=?", (record.id,))}
            for source in set(have) - {s for s, _, _ in wanted}:  # a removed repo must not stay searchable
                self._drop(db, record.id, source)
            for source, digest, make in wanted:
                if have.get(source) == digest:
                    continue
                self._drop(db, record.id, source)
                for p in make():
                    db.execute("INSERT INTO ask_fts VALUES (?,?,?,?,?,?)", (record.id, source, p["kind"], p["title"], p["location"], p["text"]))
                db.execute("INSERT INTO ask_meta VALUES (?,?,?)", (record.id, source, digest))
                changed.append(source)
        return changed

    @staticmethod
    def _drop(db, profile_id, source):
        db.execute("DELETE FROM ask_fts WHERE profile_id=? AND source=?", (profile_id, source))
        db.execute("DELETE FROM ask_meta WHERE profile_id=? AND source=?", (profile_id, source))

    def stats(self, profile_id):
        with self.store.connect() as db:
            return {r["source"]: r["n"] for r in db.execute("SELECT source, count(*) n FROM ask_fts WHERE profile_id=? GROUP BY source", (profile_id,))}

    def search(self, profile_id, query, limit=8):
        terms = words(query)
        if not terms:
            return []
        with self.store.connect() as db:
            rows = db.execute("""SELECT kind, title, location, text, source FROM ask_fts
                                 WHERE profile_id=? AND ask_fts MATCH ? ORDER BY bm25(ask_fts) LIMIT ?""",
                              (profile_id, " OR ".join('"' + t + '"' for t in terms), limit)).fetchall()
        return [dict(r) for r in rows]
