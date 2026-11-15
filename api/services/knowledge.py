"""Knowledge Library (ui/knowledge.py) and company mode (ui/company.py). Shared by every profile."""
import hashlib

from api.errors import NotFound
from core import company
from core.fetch import extract, fetch
from core.ingest import build
from core.knowledge import Library


def library(core):
    return Library(core.store)


def sources(core):
    return library(core).sources()


def search(core, query):
    return library(core).search(query) if query.strip() else []


def import_source(core, title, url, text, license, upload=None):
    """URL, pasted text or an uploaded file, in that order of preference when more than one is given."""
    lib, location, kind, body = library(core), url.strip(), "pasted", text
    if upload is not None:
        name, data = upload
        body, location, kind = extract(name, data), "file:" + name, "file"
    elif not text and location:
        location, mime, data = fetch(location)
        body, kind = extract(location, data, mime), "web"
    location = location or "pasted:" + hashlib.sha256(body.encode()).hexdigest()
    return {"result": lib.import_text(title or location, location, body, kind, license or "Unknown")}


def refresh(core, sid):
    lib = library(core)
    source = next((s for s in lib.sources() if s["id"] == sid), None)
    if source is None or source["kind"] != "web":
        raise NotFound("This source cannot be refreshed.")
    try:
        location, mime, data = fetch(source["location"])
        return {"result": lib.import_text(source["title"], source["location"], extract(location, data, mime), "web", source["license"])}
    except ValueError as exc:
        lib.failed(sid, str(exc))
        raise


def delete(core, sid):
    library(core).delete(sid)
    return {"deleted": True}


def build_base(core, progress):
    totals, failed = build(library(core), core.settings.database.parent, log=progress)
    if failed:
        raise ValueError("Could not download: " + ", ".join(failed) + ". Check git and your connection.")
    return {"imported": totals["Imported"], "unchanged": totals["Unchanged"]}


def company_list():
    return {"companies": company.companies()}


def company_problems(name, window, levels):
    rows = [r for r in company.problems(name, window) if not levels or r["Difficulty"] in levels][:30]
    return {"rows": rows, "focus": company.focus_topics(rows)}
