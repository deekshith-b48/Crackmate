"""Build scoped generation requests and reuse successfully validated local results."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
import hashlib
import json
import sqlite3
from threading import Lock
from typing import Callable

from pydantic import BaseModel, ValidationError

from core.schemas import ClaimReport, DecisionSet, Diagram, Ladder, Pitch, ProjectLesson, SkillLesson
from core.knowledge import Library
from core.llm import ModelError
from core.shared import SharedCache
from core.storage import Item, StorageError
from prompts.templates import BOUNDARY, PROMPTS


SECTIONS = {
    "Project story": "Problem, intended users, features, personal contribution, and an end-to-end request.",
    "Client side": "Components, state, APIs, validation, loading, errors, accessibility and security.",
    "Server side": "Endpoints, validation, authentication, authorisation, business logic, concurrency and failures.",
    "Database": "Data models, relationships, typical queries, indexes, transactions and consistency.",
    "Deployment and system design": "Actual deployment when known, networking, logs, bottlenecks, caching, queues, scaling and recovery.",
    "Engineering decisions": "Alternatives, trade-offs, testing, difficult bugs, limitations and improvements.",
}
LEVELS = ("Basics", "Intermediate", "Advanced")
DSA = "Data structures and algorithms"
CORE_TOPICS = (
    DSA, "Networking", "Operating systems", "Object-oriented programming",
    "Database fundamentals", "Frontend fundamentals", "Backend fundamentals",
    "Cloud and deployment fundamentals", "System design fundamentals",
)
# 41 more common interview topics; with CORE_TOPICS that makes the 50 that `python -m core.pregen` prepares.
COMMON_TOPICS = (
    "Arrays and strings", "Hash tables", "Linked lists", "Stacks and queues", "Trees and binary search trees",
    "Graphs and traversal", "Heaps and priority queues", "Recursion and backtracking", "Sorting and searching",
    "Dynamic programming", "Big-O and complexity", "Processes and threads", "Concurrency and deadlocks",
    "Memory management", "HTTP and HTTPS", "TCP vs UDP", "DNS and how a web request works", "REST APIs",
    "WebSockets and real-time communication", "SQL queries and joins", "Indexing", "Transactions and ACID",
    "SQL vs NoSQL", "SOLID principles", "Design patterns", "Caching", "Load balancing", "Message queues",
    "CAP theorem and consistency", "Sharding and replication", "Microservices vs monolith", "Rate limiting",
    "Authentication and JWT", "OAuth and sessions", "Web security basics", "Git and version control",
    "Docker and containers", "CI/CD", "Testing and TDD", "JavaScript fundamentals", "Python fundamentals",
)
GENERATION_LOCKS = tuple(Lock() for _ in range(64))


def topics(profile):
    return list(dict.fromkeys([skill for group in profile.skills.model_dump().values() for skill in group] + list(CORE_TOPICS) + list(COMMON_TOPICS)))


def target_context(profile):
    return profile.model_dump(include={"role", "company", "job_description", "experience_level"}, exclude_none=True)


@dataclass(frozen=True)
class Request:
    kind: str
    slot: str
    title: str
    context: dict
    schema: type[BaseModel]
    validate: Callable | None = None
    prepare_for_storage: Callable | None = None


def project_request(profile, project, section):
    return Request("project", f"project:{project.id}:{section}", f"{project.title} · {section}", {
        "project": project.model_dump(exclude={"id"}),
        "section": section,
        "section_scope": SECTIONS[section],
        "target": target_context(profile),
    }, ProjectLesson)


def skill_request(profile, topic, level):
    def validate(lesson):
        if (lesson.coding is not None) != (topic == DSA):
            raise ValueError("The selected topic determines whether a Python example is required.")

    stack = list(dict.fromkeys(
        [tech for project in profile.projects for tech in project.technologies]
        + [tech for group in profile.skills.model_dump().values() for tech in group]
    ))[:20]
    return Request("skill", f"skill:{level}:{topic}", f"{topic} · {level}", {
        "topic": topic, "level": level, "candidate_stack": stack, "target": target_context(profile)
    }, SkillLesson, validate)


def claims_request(profile):
    return Request("claims", "claims:all", "Resume claims", {
        "work_experience": profile.work_experience,
        "projects": [p.model_dump(exclude={"id", "reference"}) for p in profile.projects],
        "skills": profile.skills.model_dump(),
    }, ClaimReport)


def pitch_request(profile, project):
    def validate(result):
        if not 200 <= len(result.pitch.split()) <= 340:
            raise ValueError("The pitch must be about 280 spoken words.")

    return Request("pitch", f"pitch:{project.id}", f"{project.title} · 2-minute pitch", {
        "project": project.model_dump(exclude={"id"}), "target": target_context(profile),
    }, Pitch, validate)


def ladder_request(profile, slot, qid, question, answer):
    return Request("ladder", f"ladder:{qid}", f"Follow-ups · {question[:80]}", {
        "origin": slot, "question": question, "answer": answer, "target": target_context(profile),
    }, Ladder)


def diagram_request(profile, project):
    return Request("diagram", f"diagram:{project.id}", f"{project.title} · architecture", {
        "project": project.model_dump(exclude={"id"}), "target": target_context(profile),
    }, Diagram)


def generic(request):
    """The shareable form of a skill request: topic and level only, no personal stack or target."""
    context = request.context
    return replace(request, context={"topic": context["topic"], "level": context["level"],
                                     "candidate_stack": [], "target": {}})


INFERRED = "The reason is inferred from the choice itself. It is not stated in the repository."


def _enforce_honesty(decision, found):
    """Correct, never reject: confidence must be earned. An unverifiable quote is dropped, high needs a real quote, and anything lower must say what was inferred."""
    sources = {c["sha"]: c["subject"].lower() for c in found["commits"]} | {"readme": found["readme"].lower()}
    quoted = False
    for ev in decision.evidence:
        text = sources.get(ev.ref.lower())
        if ev.quote.strip():
            if text is not None and ev.quote.strip().lower() in text:
                quoted = True
            else:
                ev.quote = ""  # the model cannot be trusted to quote what it cannot show
    if decision.confidence == "high" and not quoted:
        decision.confidence = "medium"
    if decision.confidence != "high" and not decision.assumption.strip():
        decision.assumption = INFERRED


def decisions_request(profile, project, found):
    from core.career.decisions import allowed_refs, canonical_ref
    allowed = allowed_refs(found)

    def validate(result):  # every citation must exist in the evidence we supplied: no invented sources
        for decision in result.decisions:
            for ev in decision.evidence:
                ref = canonical_ref(ev.ref)
                if ref not in allowed:
                    raise ValueError(f"Evidence {ev.ref!r} is not in the supplied commits, README or dependencies.")
                ev.ref = "README" if ref == "readme" else ref  # store the canonical form
            _enforce_honesty(decision, found)

    return Request("decisions", f"decisions:{project.id}", f"{project.title} · decisions", {
        "project": project.model_dump(exclude={"id", "reference"}), "candidates": found, "target": target_context(profile),
    }, DecisionSet, validate)


class Material:
    enrich = None  # optional hook(record, request) -> request, used to add facts read from a project's repository

    def _enrich(self, record, request):
        return self.enrich(record, request) if self.enrich else request

    def __init__(self, store, model):
        self.store = store
        self.model = model
        self.library = Library(store)
        self.cache = SharedCache(store)

    def models(self):
        settings = self.model.settings
        return [m for m in dict.fromkeys((settings.model, settings.fallback_model)) if m]

    def shared_body(self, request, evidence=None):
        """Saved shared lesson text for this skill request, or None."""
        if request.kind != "skill":
            return None
        source = generic(request)
        evidence = self.evidence(source) if evidence is None else evidence
        return next((body for m in self.models() if (body := self.cache.get(self.digest(source, m, evidence)))), None)

    def evidence(self, request):
        if request.kind not in ("skill", "project"):
            return []
        context = request.context
        query = " ".join([context.get("topic", ""), context.get("section", ""),
                          *context.get("project", {}).get("technologies", [])])
        return self.library.search(query)

    def digest(self, request, model, evidence=None):
        prompt = PROMPTS[request.kind]
        settings = self.model.settings
        data = {
            "kind": request.kind, "context": request.context, "model": model,
            "retrieval": [(p["id"], p["hash"]) for p in (self.evidence(request) if evidence is None else evidence)],
            "primary_model": settings.model, "fallback_model": settings.fallback_model,
            "temperature": self.model.temperature, "prompt": BOUNDARY + prompt.instructions,
            "version": prompt.version, "tokens": prompt.tokens,
            "format": "json_object", "schema": request.schema.model_json_schema(),
        }
        encoded = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def current(self, record, request, item):
        request = self._enrich(record, request)
        settings = self.model.settings
        models = {settings.model, settings.fallback_model} - {""}
        return (
            item is not None and item.model in models
            and item.digest == self.digest(request, item.model)
            and (request.kind != "plan" or record.revision == item.revision)
        )

    def _saved(self, request):
        """A model call the cache made unnecessary."""
        sink = getattr(self.model, "usage_sink", None)
        if callable(sink):
            try:
                sink(request.kind, "cache", 0, 0, True)
            except Exception:  # noqa: BLE001
                pass

    def _fresh(self, request, evidence, progress):
        """Ask the model for one lesson and validate it. Returns (result, model)."""
        def validate(result):
            if request.validate:
                request.validate(result)
            if request.kind in ("skill", "project"):
                validate_citations(result, evidence)
        context = dict(request.context)
        if request.kind in ("skill", "project"):
            context["source_passages"] = evidence
        result, model = self.model.generate(request.kind, context, request.schema, validate=validate, progress=progress)
        if request.kind in ("skill", "project"):
            result.evidence = evidence
        return result, model

    def warm(self, request, progress=lambda _: None):
        """Fill the shared cache for a skill without touching any profile. True if it called the model."""
        source = generic(request)
        evidence = self.evidence(source)
        if self.shared_body(request, evidence):
            return False
        result, model = self._fresh(source, evidence, progress)
        self.cache.put(self.digest(source, model, evidence), request.title, model, result.model_dump_json())
        return True

    def generate(self, record, request, *, regenerate=False, tailor=False, progress=lambda _: None):
        """Skill lessons use the shared cache unless tailor=True (then they stay private to this profile)."""
        request = self._enrich(record, request)
        lock = GENERATION_LOCKS[hash((record.id, request.slot)) % len(GENERATION_LOCKS)]
        with lock:
            item = self.store.item(record.id, request.slot)
            if not regenerate and self.current(record, request, item):
                self._saved(request)
                return item, False
            evidence = self.evidence(request)
            shared = request.kind == "skill" and not tailor
            source = generic(request) if shared else request
            if shared and not regenerate and (body := self.shared_body(request, evidence)):
                try:
                    request.schema.model_validate_json(body)
                except ValidationError:
                    body = None
                if body:
                    progress("Loaded the shared lesson instantly.")
                    self._saved(request)
                    model = next(m for m in self.models() if self.cache.get(self.digest(source, m, evidence)) == body)
                    item = Item(request.slot, request.kind, request.title, self.digest(request, model, evidence),
                                model, record.revision, body)
                    self.store.save_item(record, item)
                    return item, False
            result, model = self._fresh(source, evidence, progress)
            if request.prepare_for_storage:
                result = request.prepare_for_storage(result)
            if shared:
                self.cache.put(self.digest(source, model, evidence), request.title, model, result.model_dump_json())
            item = Item(
                request.slot, request.kind, request.title, self.digest(request, model, evidence),
                model, record.revision, result.model_dump_json()
            )
            self.store.save_item(record, item)
            return item, True


def lesson_requests(profile):
    for project in profile.projects:
        for section in SECTIONS:
            yield project_request(profile, project, section)
    for topic in topics(profile):
        for level in LEVELS:
            yield skill_request(profile, topic, level)


def validate_citations(result, evidence, required=False):
    passages = {p["id"]: p for p in evidence}
    for citation in result.citations:
        passage = passages.get(citation.passage_id)
        if passage is None:
            raise ValueError("Citation refers to an unavailable passage.")
        if citation.quote and citation.quote not in passage["text"]:
            raise ValueError("Quotation does not match the cited passage.")
    if required and evidence and not result.citations:
        raise ValueError("Use citations for supported claims or explain the evidence gap.")


def generate_many(material, record, requests, *, workers=3, progress=lambda _: None):
    """Generate missing or outdated lessons in parallel. Returns (done, titles_that_failed).
    shortcut: 3 workers keeps free-tier Groq rate limits happy; raise it on a paid plan."""
    todo = [r for r in requests if not material.current(record, r, material.store.item(record.id, r.slot))]
    done, failed = 0, []
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(material.generate, record, r): r for r in todo}
        for future in as_completed(futures):
            try:
                future.result()
                done += 1
            except (ModelError, StorageError, ValueError, sqlite3.Error):
                failed.append(futures[future].title)
            progress(f"{done + len(failed)} of {len(todo)} sections finished…")  # main thread only
    return done, failed
