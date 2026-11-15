"""Usage log: every model call, and every call a cache saved. Logging can never break a request."""
from datetime import datetime, timedelta, timezone
import os
import sqlite3

# Groq's free tier allows about this many tokens per model per day (shared by your whole organisation).
DAILY_TOKENS = int(os.environ.get("GROQ_DAILY_TOKENS", "200000"))
DEFAULT_SAVED = 2500  # tokens a cached answer is assumed to save when we have no history for that feature


class Usage:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS usage(
                ts TEXT NOT NULL, feature TEXT NOT NULL, model TEXT NOT NULL,
                tokens_in INTEGER NOT NULL, tokens_out INTEGER NOT NULL, cached INTEGER NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS usage_ts ON usage(ts)")

    def add(self, feature, model, tokens_in=0, tokens_out=0, cached=False):
        try:
            with self.store.connect() as db:
                db.execute("INSERT INTO usage VALUES (?,?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(), feature or "other", model,
                                                                      int(tokens_in or 0), int(tokens_out or 0), int(bool(cached))))
        except (sqlite3.Error, TypeError, ValueError):
            pass  # a full disk or a locked database must never fail the user's request

    def summary(self, hours=24):
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self.store.connect() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM usage WHERE ts >= ?", (since,))]
            week = [dict(r) for r in db.execute("SELECT * FROM usage WHERE ts >= ?", ((datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),))]
        live, hit = [r for r in rows if not r["cached"]], [r for r in rows if r["cached"]]
        features = {}
        for r in rows:
            f = features.setdefault(r["feature"], {"feature": r["feature"], "calls": 0, "cached": 0, "tokens": 0})
            f["cached" if r["cached"] else "calls"] += 1
            f["tokens"] += r["tokens_in"] + r["tokens_out"]
        average = {k: v["tokens"] / v["calls"] for k, v in features.items() if v["calls"]}
        saved = round(sum(average.get(r["feature"], DEFAULT_SAVED) for r in hit))
        models = {}
        for r in live:
            models[r["model"]] = models.get(r["model"], 0) + r["tokens_in"] + r["tokens_out"]
        days = {}
        for r in week:
            d = days.setdefault(r["ts"][:10], {"date": r["ts"][:10], "calls": 0, "cached": 0, "tokens": 0})
            d["cached" if r["cached"] else "calls"] += 1
            d["tokens"] += r["tokens_in"] + r["tokens_out"]
        return {
            "window_hours": hours, "calls": len(live), "cached": len(hit), "saved_tokens": saved,
            "tokens_in": sum(r["tokens_in"] for r in live), "tokens_out": sum(r["tokens_out"] for r in live),
            "by_feature": sorted(features.values(), key=lambda f: -f["tokens"]),
            "by_model": [{"model": m, "tokens": t, "limit": DAILY_TOKENS, "remaining": max(0, DAILY_TOKENS - t)} for m, t in sorted(models.items(), key=lambda kv: -kv[1])],
            "days": sorted(days.values(), key=lambda d: d["date"]),
            "note": "Counted from this app only. Groq's daily limit is shared by your whole organisation, so the real headroom can be lower.",
        }
