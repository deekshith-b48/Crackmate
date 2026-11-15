"""Company mode: the DSA problems a company tags most, fetched at runtime and never committed.

Data: github.com/liquidslr/leetcode-company-wise-problems. We keep a short-lived local cache and show
titles with links to LeetCode. Problem statements are not copied.
"""
import csv
import hashlib
import io
import json
import time
from collections import Counter
from urllib.parse import quote

from core.config import ROOT
from core.fetch import fetch

REPO = "liquidslr/leetcode-company-wise-problems"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/"
LISTING = f"https://api.github.com/repos/{REPO}/contents/"
WINDOWS = {"Last 30 days": "1. Thirty Days.csv", "3 months": "2. Three Months.csv",
           "6 months": "3. Six Months.csv", "Over 6 months": "4. More Than Six Months.csv",
           "All time": "5. All.csv"}
CACHE = ROOT / ".crackmate" / "company"
# Used when company data is unreachable.
FALLBACK_TOPICS = ("Array", "String", "Hash Table", "Two Pointers", "Sliding Window", "Binary Search",
                   "Stack", "Linked List", "Tree", "Graph", "Heap", "Backtracking", "Greedy", "Dynamic Programming")


def cached(url, hours=24):
    CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".txt")
    if path.exists() and time.time() - path.stat().st_mtime < hours * 3600:
        return path.read_text(encoding="utf-8")
    try:
        text = fetch(url)[2].decode("utf-8-sig")
    except (ValueError, UnicodeDecodeError):
        if path.exists():  # stale data beats none
            return path.read_text(encoding="utf-8")
        raise ValueError("Company data could not be loaded. Check your connection.") from None
    path.write_text(text, encoding="utf-8")
    return text


def companies():
    items = json.loads(cached(LISTING))
    return sorted(i["name"] for i in items if i.get("type") == "dir" and not i["name"].startswith("."))


def parse_problems(text):
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        link = (row.get("Link") or "").strip()
        if not link.startswith("https://leetcode.com/problems/"):  # never show other links from third-party data
            continue
        try:
            frequency = float(row.get("Frequency") or 0)
        except ValueError:
            frequency = 0.0
        rows.append({
            "Title": (row.get("Title") or "").strip()[:150], "Difficulty": (row.get("Difficulty") or "").strip().title(),
            "Frequency": frequency, "Topics": ", ".join(t.strip() for t in (row.get("Topics") or "").split(",") if t.strip()),
            "Link": link,
        })
        if len(rows) >= 2000:
            break
    return sorted(rows, key=lambda r: -r["Frequency"])


def problems(company, window):
    return parse_problems(cached(RAW + quote(company) + "/" + quote(WINDOWS[window])))


def focus_topics(rows, count=8):
    return Counter(t for r in rows for t in r["Topics"].split(", ") if t).most_common(count)
