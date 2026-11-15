"""Pre-generate the 50 most common topics once, so popular lessons load instantly for every profile.

Run from the project folder:  .venv/bin/python -m core.pregen [--levels Basics Intermediate] [--workers 2]
Needs your Groq key (environment or .streamlit/secrets.toml). Safe to re-run: finished lessons are skipped,
and a rate limit only slows it down. Free Groq limits mean the first run can take a while.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import sqlite3
import sys
import time
import tomllib

from core.config import ROOT, Settings
from core.llm import ModelError, ModelService
from core.material import COMMON_TOPICS, CORE_TOPICS, LEVELS, Material, skill_request
from core.schemas import Profile
from core.storage import Storage

PREGEN_TOPICS = CORE_TOPICS + COMMON_TOPICS


def warm_patiently(material, request, tries=8):
    """Batch jobs wait out rate limits instead of failing: sleep what Groq asks (at most 90 s) and retry."""
    for attempt in range(tries):
        try:
            return material.warm(request)
        except ModelError as exc:
            # A long wait means a daily or hourly token budget is spent: stop instead of burning attempts.
            if not exc.try_next or attempt == tries - 1 or exc.retry_after > 120:
                raise
            time.sleep(min(exc.retry_after or 30, 90))


def warm_all(material, levels=("Basics",), workers=2, log=print):
    """Fill the shared cache. Returns (generated, already_cached, failed_titles)."""
    requests = [skill_request(Profile(), topic, level) for level in levels for topic in PREGEN_TOPICS]
    generated, cached, failed = 0, 0, []
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(warm_patiently, material, r): r for r in requests}
        for number, future in enumerate(as_completed(futures), 1):
            try:
                generated, cached = (generated + 1, cached) if future.result() else (generated, cached + 1)
            except (ModelError, ValueError, sqlite3.Error):
                failed.append(futures[future].title)
            log(f"{number}/{len(requests)} · {generated} generated, {cached} already cached, {len(failed)} failed")
    return generated, cached, failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", nargs="+", default=["Basics"], choices=LEVELS)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    secrets_file = ROOT / ".streamlit" / "secrets.toml"
    secrets = tomllib.loads(secrets_file.read_text()) if secrets_file.exists() else {}
    settings = Settings.load(secrets)
    if not settings.api_key:
        sys.exit("Set GROQ_API_KEY in your environment or .streamlit/secrets.toml first.")
    store = Storage(settings.database)
    done, cached, failed = warm_all(Material(store, ModelService(settings)), args.levels, args.workers)
    print(f"Done. {done} generated, {cached} already cached.")
    if failed:
        print("Failed (re-run to retry):", "; ".join(failed))
        sys.exit(1)
