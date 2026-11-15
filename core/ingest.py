"""Build the knowledge base: shallow-clone public study repos, import their Markdown, delete the clones.

Run from the project folder:  .venv/bin/python -m core.ingest
Nothing is copied into the repo. Text goes into the local database with a link back to the original
and its license. Re-running is safe: unchanged files are skipped.
"""
from collections import Counter
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from core.config import Settings
from core.knowledge import Library
from core.storage import Storage

# name, URL, license (read from each repo's LICENSE file on 2026-11-14), sub-folder to read
REPOS = (
    ("System Design Primer", "https://github.com/donnemartin/system-design-primer", "CC BY 4.0 · Donne Martin", ""),
    ("Tech Interview Handbook", "https://github.com/yangshun/tech-interview-handbook", "MIT · Yangshun Tay", "apps/website/contents"),
    ("Coding Interview University", "https://github.com/jwasham/coding-interview-university", "CC BY-SA 4.0 · John Washam", ""),
)
SKIP_DIRS = {"translations", "node_modules", "blog"}
MAX_TEXT = 90_000  # the library accepts 100,000 characters per source


def wanted(relative: Path):
    parts = relative.parts
    return not (any(p.startswith(".") or p in SKIP_DIRS for p in parts[:-1])
                or re.fullmatch(r"README-.+\.md", parts[-1]))  # root-level translations


def sections(text):
    """Whole file if small, otherwise one piece per '## ' section."""
    if len(text) <= MAX_TEXT:
        return [("", text)]
    pieces = (p for p in re.split(r"(?m)^(?=## )", text) if len(p.strip()) >= 200)
    return [(p.splitlines()[0].lstrip("# ").strip(), p[:MAX_TEXT]) for p in pieces]


def page_title(text, fallback):
    front = re.match(r"---\n(.*?)\n---", text, re.S)
    if front and (m := re.search(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$", front.group(1))):
        return m.group(1)
    prose = re.sub(r"(?s)```.*?```|~~~.*?~~~", "", text)  # '#' inside code is a comment, not a heading
    m = re.search(r"(?m)^# (.+)$", prose)
    return m.group(1).strip() if m else fallback


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def ingest(library, clone_root, repos=REPOS, log=print):
    """Import Markdown from already-cloned repos under clone_root. Returns a Counter of outcomes."""
    totals = Counter()
    for name, url, license, folder in repos:
        root = Path(clone_root) / slug(name)
        if not root.is_dir():
            continue
        for path in sorted((root / folder).rglob("*.md")):
            relative = path.relative_to(root)
            # Cloned files are untrusted: skip links that could point outside the clone.
            if not wanted(relative) or path.is_symlink() or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            page = page_title(text, path.stem)
            for section, body in sections(text):
                if len(body.strip()) < 200:
                    continue
                title = f"{name} · {page}" + (f" · {section}" if section else "")
                location = f"{url}/blob/HEAD/{relative.as_posix()}" + (f"#{slug(section)}" if section else "")
                totals[library.import_text(title[:200], location, body, "repo", license, bulk=True)] += 1
        log(f"{name}: done ({sum(totals.values())} sections so far)")
    return totals


def clone(url, destination):
    subprocess.run(["git", "clone", "--depth", "1", "--single-branch", "--quiet", url, str(destination)],
                   check=True, capture_output=True, timeout=300)


def build(library, directory, log=print, repos=REPOS):
    """Clone each repo into a temporary folder, import it, and delete the clone."""
    failed = []
    with tempfile.TemporaryDirectory(dir=directory) as scratch:
        for name, url, *_ in repos:
            log(f"Downloading {name}…")
            try:
                clone(url, Path(scratch) / slug(name))
            except (OSError, subprocess.SubprocessError):
                failed.append(name)
        totals = ingest(library, scratch, repos, log)
    return totals, failed


if __name__ == "__main__":
    settings = Settings.load({})
    store = Storage(settings.database)
    totals, failed = build(Library(store), settings.database.parent)
    print(dict(totals))
    if failed:
        print("Could not download (is git installed and are you online?):", ", ".join(failed))
        sys.exit(1)
