"""Attach a GitHub repository to a project, analyse it once, and re-analyse only when its commit changes."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from core.career import facts as facts_mod
from core.career import gitlog, secrets
from core.config import ROOT

URL = re.compile(r"^https://github\.com/([\w.\-]+)/([\w.\-]+?)(?:\.git)?/?$")
REPOS = Path(os.environ.get("CRACKMATE_REPOS") or ROOT / ".crackmate" / "repos")
MAX_BYTES = 300 * 1024**2
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


class RepoError(ValueError):
    pass


def validate_url(url):
    match = URL.match(url.strip())
    if not match:
        raise RepoError("Use a public GitHub repository URL like https://github.com/owner/repo.")
    return f"https://github.com/{match.group(1)}/{match.group(2)}"


def remote_head(url):
    out = subprocess.run(["git", "ls-remote", url, "HEAD"], capture_output=True, text=True, timeout=60, env=ENV, check=False)
    return out.stdout.split()[0] if out.returncode == 0 and out.stdout.strip() else ""


def clone(url, dest):
    """Shallow clone. Hooks from the repo never run, and the file:// transport is blocked."""
    try:
        subprocess.run(["git", "-c", "protocol.file.allow=never", "clone", "--depth", "300", "--single-branch", "--no-tags", "--quiet", url, str(dest)],
                       check=True, capture_output=True, timeout=300, env=ENV)
    except (OSError, subprocess.SubprocessError):
        shutil.rmtree(dest, ignore_errors=True)
        raise RepoError("The repository could not be downloaded. Check that it is public and the URL is right.") from None


def head_commit(root):
    out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30, check=False)
    return out.stdout.strip()


def folder_size(root):
    return sum(f.stat().st_size for f in Path(root).rglob("*") if f.is_file() and not f.is_symlink())


def analyse(root, identities):
    """Everything we can know from the files and history, with no model call."""
    files = facts_mod.read_repo(root)
    found = facts_mod.detect(files)
    commits = gitlog.parse_log(gitlog.read_log(root))
    return {"facts": found, "authors": gitlog.authors(commits)[:12], "ownership": gitlog.ownership(commits, identities),
            "hotspots": gitlog.hotspots(commits, identities), "secrets": secrets.scan(files),
            "first_commit": min((c["time"] for c in commits), default=0), "last_commit": max((c["time"] for c in commits), default=0)}


def input_hash(url, commit):
    return hashlib.sha256(f"{url}@{commit}".encode()).hexdigest()[:16]


class Repos:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS career_repos(
                profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE, project_id TEXT NOT NULL,
                url TEXT NOT NULL, commit_sha TEXT NOT NULL, input_hash TEXT NOT NULL, identities TEXT NOT NULL,
                summary TEXT NOT NULL, indexed_at TEXT NOT NULL, PRIMARY KEY (profile_id, project_id))""")

    def get(self, profile_id, project_id):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM career_repos WHERE profile_id=? AND project_id=?", (profile_id, project_id)).fetchone()
        return self._view(row) if row else None

    def all(self, profile_id):
        with self.store.connect() as db:
            return [self._view(r) for r in db.execute("SELECT * FROM career_repos WHERE profile_id=?", (profile_id,))]

    @staticmethod
    def _view(row):
        return {"project_id": row["project_id"], "url": row["url"], "commit": row["commit_sha"], "input_hash": row["input_hash"],
                "identities": json.loads(row["identities"]), "indexed_at": row["indexed_at"], **json.loads(row["summary"])}

    def save(self, profile_id, project_id, url, commit, identities, summary):
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO career_repos VALUES (?,?,?,?,?,?,?,?)", (
                profile_id, project_id, url, commit, input_hash(url, commit), json.dumps(identities), json.dumps(summary),
                datetime.now(timezone.utc).isoformat()))

    def remove(self, profile_id, project_id):
        with self.store.connect() as db:
            db.execute("DELETE FROM career_repos WHERE profile_id=? AND project_id=?", (profile_id, project_id))
        shutil.rmtree(REPOS / profile_id / project_id, ignore_errors=True)


def index(store, profile_id, project_id, url, *, identities=None, force=False, progress=lambda _: None, cloner=None, head=None):
    """Download (if the commit changed) and analyse. Returns (view, changed)."""
    repos, cloner, head = Repos(store), cloner or clone, head or remote_head
    url = validate_url(url)
    saved = repos.get(profile_id, project_id)
    dest = REPOS / profile_id / project_id
    progress("Checking the repository for changes…")
    latest = head(url)
    if saved and not force and saved["url"] == url and latest and latest == saved["commit"] and dest.is_dir():
        return saved, False  # same commit: nothing to re-read
    progress("Downloading the repository (shallow)…")
    shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    cloner(url, dest)
    if folder_size(dest) > MAX_BYTES:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepoError("This repository is larger than 300 MB. Choose a smaller one or a focused sub-project.")
    progress("Reading dependencies, imports and structure…")
    ids = identities if identities is not None else (saved["identities"] if saved else [])
    summary = analyse(dest, ids)
    progress("Reading the commit history and scanning for secrets…")
    repos.save(profile_id, project_id, url, head_commit(dest), ids, summary)
    return repos.get(profile_id, project_id), True


def set_identities(store, profile_id, project_id, identities):
    repos, saved = Repos(store), Repos(store).get(profile_id, project_id)
    if saved is None:
        raise RepoError("Attach a repository first.")
    dest = REPOS / profile_id / project_id
    summary = analyse(dest, identities) if dest.is_dir() else {k: saved[k] for k in ("facts", "authors", "ownership", "hotspots", "secrets", "first_commit", "last_commit")}
    repos.save(profile_id, project_id, saved["url"], saved["commit"], identities, summary)
    return repos.get(profile_id, project_id)
