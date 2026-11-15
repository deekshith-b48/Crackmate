"""Candidate engineering decisions found in a repository. Deterministic: the model only writes up what is found here."""
import re
from pathlib import Path

from core.career import gitlog

KEYWORDS = re.compile(
    r"\b(switch|migrat|replace|refactor|rewrite|moved? to|instead of|optimi[sz]|cach|queue|index|rate.?limit|scal|"
    r"fix(?:es|ed)?\s+(?:race|leak|deadlock|memory|crash)|introduce|auth|jwt|oauth|websocket|socket|docker|database|postgres|mongo|redis)", re.I)
NOISE = re.compile(r"^(chore|ci|docs?|build|style|bump|deps?|release|merge)\b|dependabot|\bbump\b|\bsponsor|\bscorecard|\bcodeql", re.I)
README_NAMES = ("README.md", "README.MD", "readme.md", "README.rst", "README.txt", "README")


def readme_excerpt(root, limit=1800):
    for name in README_NAMES:
        path = Path(root) / name
        if path.is_file() and not path.is_symlink():
            text = path.read_text(encoding="utf-8", errors="ignore")
            text = re.sub(r"!\[[^\]]*\]\([^)]*\)|<img[^>]*>|\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", "", text)  # badges and images are noise
            return text.strip()[:limit]
    return ""


def candidates(root, identities, stack, limit=15):
    """Commits whose message sounds like a decision, the README, and the dependency choices. The model may cite only these."""
    commits = gitlog.parse_log(gitlog.read_log(root, limit=400))
    picks = [{"sha": c["sha"][:7], "subject": c["subject"][:140], "yours": gitlog.is_me(c, identities)} for c in commits if KEYWORDS.search(c["subject"]) and not NOISE.search(c["subject"])][:limit]
    return {"commits": picks, "readme": readme_excerpt(root), "dependencies": sorted(stack)[:20]}


def canonical_ref(ref):
    """Models write 'commit 98f2ef4', 'README.md' or a 40-char sha. Map harmless variants to the form we supplied."""
    r = re.sub(r"^(commit|sha|hash)[:\s]+", "", ref.strip().lower())
    if r.startswith("readme"):
        return "readme"
    return r[:7] if re.fullmatch(r"[0-9a-f]{7,40}", r) else r


def allowed_refs(found):
    return {c["sha"] for c in found["commits"]} | ({"readme"} if found["readme"] else set()) | {d.lower() for d in found["dependencies"]}
