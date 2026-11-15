"""Hybrid retrieval: your private index and the shared knowledge base, merged by reciprocal-rank fusion.

Both are keyword (BM25) searches. There are no embeddings, so there is no extra download and nothing leaves your computer.
"""
from core.ask.index import AskIndex
from core.knowledge import Library

RRF = 60  # standard constant: a rank-1 result scores 1/61, so no single list can dominate


def hybrid(core, record, query, k=6):
    index = AskIndex(core.store)
    index.refresh(core, record)
    personal = index.search(record.id, query, 8)
    shared = Library(core.store).search(query)
    scored = {}
    for lists, weight in ((personal, 1.0), (shared, 0.9)):
        for rank, row in enumerate(lists):
            kind = row.get("kind") or "knowledge"
            title = row["title"] + (f" · {row['heading']}" if row.get("heading") else "")
            key = (row.get("location", ""), row["text"][:80])
            entry = scored.setdefault(key, {"kind": kind, "title": title, "location": row.get("location", ""), "text": row["text"],
                                            "license": row.get("license", ""), "score": 0.0})
            entry["score"] += weight / (RRF + rank + 1)
    best = sorted(scored.values(), key=lambda e: -e["score"])[:k]
    return [{"n": i, **{f: e[f] for f in ("kind", "title", "location", "license")}, "text": e["text"][:900]} for i, e in enumerate(best, 1)]
