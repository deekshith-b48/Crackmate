"""Authorship, ownership and hotspots from `git log`. Deterministic: no model, no repo code is run."""
import math
import subprocess
from collections import defaultdict
from pathlib import PurePosixPath

from core.career.facts import LANGUAGES

FORMAT = "@@%H%x1f%ae%x1f%an%x1f%at%x1f%s"


def read_log(root, limit=2000):
    out = subprocess.run(["git", "-C", str(root), "log", "--no-merges", f"-n{limit}", "--numstat", f"--format={FORMAT}"],
                         capture_output=True, text=True, timeout=60, check=False)
    return out.stdout if out.returncode == 0 else ""


def parse_log(text):
    commits, current = [], None
    for line in text.splitlines():
        if line.startswith("@@"):
            sha, email, name, when, subject = (line[2:].split("\x1f") + [""] * 5)[:5]
            current = {"sha": sha, "email": email.lower(), "name": name, "time": int(when or 0), "subject": subject, "files": []}
            commits.append(current)
        elif current is not None and line.count("\t") == 2:
            added, deleted, path = line.split("\t")
            if added.isdigit() and deleted.isdigit():  # binary files show "-"
                current["files"].append((path, int(added), int(deleted)))
    return commits


def is_me(commit, identities):
    ids = {i.strip().lower() for i in identities if i.strip()}
    return commit["email"] in ids or commit["name"].lower() in ids


def authors(commits):
    table = defaultdict(lambda: {"name": "", "email": "", "commits": 0, "added": 0})
    for c in commits:
        row = table[c["email"]]
        row.update(name=c["name"], email=c["email"])
        row["commits"] += 1
        row["added"] += sum(f[1] for f in c["files"])
    return sorted(table.values(), key=lambda r: -r["added"])


def ownership(commits, identities):
    """Your share overall, plus per file: files you mostly wrote versus files you will be asked about but did not write."""
    mine = [c for c in commits if is_me(c, identities)]
    total = sum(f[1] for c in commits for f in c["files"])
    my_added = sum(f[1] for c in mine for f in c["files"])
    per_file = defaultdict(lambda: [0, 0])  # path -> [mine, all]
    for c in commits:
        for path, added, _ in c["files"]:
            per_file[path][1] += added
            if is_me(c, identities):
                per_file[path][0] += added
    rows = [{"path": p, "yours": round(m / a, 2), "lines": a} for p, (m, a) in per_file.items() if a >= 20]
    rows.sort(key=lambda r: -r["lines"])
    return {"identified": bool(identities), "commits": len(commits), "your_commits": len(mine),
            "share": round(my_added / total, 2) if total else 0.0,
            "files_yours": [r for r in rows if r["yours"] >= 0.5][:8],
            "files_not_yours": [r for r in rows if r["yours"] < 0.2][:8] if identities else []}


def hotspots(commits, identities, limit=8):
    """Files changed most often and most heavily are where the hard problems were: good 'a challenge I solved' stories."""
    stat = defaultdict(lambda: {"commits": 0, "churn": 0, "mine": 0})
    for c in commits:
        mine = is_me(c, identities)
        for path, added, deleted in c["files"]:
            if PurePosixPath(path).suffix.lower() not in LANGUAGES:  # package.json, READMEs and CI files change often but hide no story
                continue
            s = stat[path]
            s["commits"] += 1
            s["churn"] += added + deleted
            s["mine"] += mine
    rows = [{"path": p, "commits": s["commits"], "churn": s["churn"], "your_commits": s["mine"],
             "score": round(s["commits"] * (1 + math.log1p(s["churn"])), 1)} for p, s in stat.items() if s["commits"] > 1]
    return sorted(rows, key=lambda r: -r["score"])[:limit]
