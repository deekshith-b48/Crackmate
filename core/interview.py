"""Interview snapshots use optimistic transactions and stable turn identifiers."""
from typing import Literal
from uuid import uuid4
from pydantic import Field
from core.schemas import Data, Question, Feedback
from core.storage import StorageError
from core.material import GENERATION_LOCKS, Material, skill_request, project_request, validate_citations


MODES = ("Project deep-dive", "Technical fundamentals", "DSA reasoning", "System design", "Behavioural and HR", "Mixed interview")


class PlannedQuestion(Question):
    kind: Literal["technical", "behavioural"] = "technical"


class QuestionPlan(Data):
    questions: list[PlannedQuestion] = Field(min_length=1, max_length=10)


class Turn(Data):
    id: str = Field(default_factory=lambda: uuid4().hex)
    question: PlannedQuestion
    original: str = ""
    confirmed: str = ""
    recording_hash: str = ""
    hint_used: bool = False
    topic: str = ""
    difficulty: str = ""
    feedback: Feedback | None = None
    outcome: Literal["pending", "answered", "skipped"] = "pending"
    depth: int = 0
    retries: list[Feedback] = Field(default_factory=list)
    previous_answers: list[str] = Field(default_factory=list)


class Session(Data):
    id: str = Field(default_factory=lambda: uuid4().hex)
    profile_id: str
    revision: int = 1
    mode: str
    topic: str
    project_id: str = ""
    difficulty: str
    coach: bool = True
    spoken: bool = False
    budget: int = Field(ge=1, le=10)
    state: Literal["question ready", "transcript review", "feedback ready", "paused", "completed", "abandoned"] = "question ready"
    resume_state: str = "question ready"
    index: int = 0
    turns: list[Turn]
    context: dict = Field(default_factory=dict)


class Interviews:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS interviews(
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL, body TEXT NOT NULL)""")

    def list(self, profile_id):
        with self.store.connect() as db:
            return [Session.model_validate_json(row[0]) for row in db.execute(
                "SELECT body FROM interviews WHERE profile_id=? ORDER BY rowid DESC", (profile_id,))]

    def get(self, ident, profile_id):
        return next((s for s in self.list(profile_id) if s.id == ident), None)

    def create(self, session):
        with self.store.connect() as db:
            db.execute("INSERT INTO interviews VALUES(?,?,?,?)",
                       (session.id, session.profile_id, session.revision, session.model_dump_json()))
        return session

    def save(self, session):
        updated = session.model_copy(update={"revision": session.revision + 1}, deep=True)
        with self.store.connect() as db:
            cursor = db.execute("UPDATE interviews SET revision=?,body=? WHERE id=? AND profile_id=? AND revision=?",
                                (updated.revision, updated.model_dump_json(), session.id, session.profile_id, session.revision))
            if cursor.rowcount != 1:
                raise StorageError("This interview changed in another tab. Reload before continuing.")
        return updated

    def delete(self, ident, profile_id):
        with self.store.connect() as db:
            db.execute("DELETE FROM interviews WHERE id=? AND profile_id=?", (ident, profile_id))


def confirm(session, text):
    if session.state not in ("question ready", "transcript review"):
        raise ValueError("This answer cannot be changed at the current stage.")
    if not text.strip() or len(text) > 3500:
        raise ValueError("Confirm an answer between 1 and 3,500 characters.")
    session.turns[session.index].confirmed = text.strip()
    session.state = "transcript review"


def advance(session, *, skip=False, follow=False):
    turn = session.turns[session.index]
    if session.state not in ("question ready", "transcript review", "feedback ready"):
        raise ValueError("Resume this interview first.")
    if not skip and not turn.feedback:
        raise ValueError("Evaluate or skip the answer first.")
    if skip:
        turn.outcome = "skipped"
    if follow and turn.feedback and turn.depth == 0 and session.index + 1 < session.budget:
        question = turn.feedback.follow_up
        if question not in [t.question.question for t in session.turns]:
            session.turns[session.index + 1] = Turn(
                question=PlannedQuestion(question=question, answer="Evaluate the candidate's reasoning using the original context.",
                                         hint="Explain the underlying mechanism and give an example.",kind=turn.question.kind),
                depth=1,
            )
    session.index += 1
    session.state = "completed" if session.index >= session.budget else "question ready"


def evaluate(repository, service, record, session, progress):
    lock = GENERATION_LOCKS[hash(session.id) % len(GENERATION_LOCKS)]
    with lock:
        latest = repository.get(session.id, record.id)
        if latest is None:
            raise StorageError("This interview has been deleted.")
        if latest.revision != session.revision:
            if latest.index == session.index and latest.turns[latest.index].feedback:
                return latest
            raise StorageError("The interview changed. Reload and retry.")
        turn = session.turns[session.index]
        if session.state != "transcript review" or not turn.confirmed:
            raise ValueError("Confirm the transcript before evaluation.")
        if turn.feedback:
            return session
        request = skill_request(record.profile, turn.topic or session.topic, turn.difficulty or session.difficulty)
        if session.project_id:
            project = next((p for p in record.profile.projects if p.id == session.project_id), None)
            if project:
                request = project_request(record.profile, project, "Engineering decisions")
        evidence = Material(repository.store, service).evidence(request)
        context = {
            "question": turn.question.question, "example_answer": turn.question.answer,
            "candidate_answer": turn.confirmed, "lesson_context": request.context,
            "interview_kind": turn.question.kind, "source_passages": evidence,
        }
        feedback, _ = service.generate(
            "feedback", context, Feedback,
            validate=lambda result: validate_citations(result, evidence, required=False), progress=progress,
        )
        feedback.evidence = evidence
        from core.learning import RUBRIC, utcnow
        feedback.learning_metadata = {
            "time": utcnow().isoformat(),
            "rubric": RUBRIC if turn.question.kind == "technical" else "behavioural-0-4-v1",
            "difficulty": turn.difficulty or session.difficulty, "hint": turn.hint_used,
            "revealed": False, "retry": bool(turn.retries),
            "independent": not turn.hint_used and not turn.retries,
        }
        turn.feedback = feedback
        turn.outcome = "answered"
        session.state = "feedback ready"
        return repository.save(session)


def report(session):
    """Scores use the latest successful answer per question, with retries shown separately."""
    from core.export import evidence_markdown
    dimensions = ("accuracy", "coverage", "reasoning", "clarity")
    answered = [t for t in session.turns if t.feedback]
    skipped = sum(t.outcome == "skipped" for t in session.turns)
    lines = ["# Mock interview report", f"Mode · {session.mode}", f"State · {session.state}",
             f"Scored {len(answered)} · Skipped {skipped} · Retries {sum(len(t.retries) for t in session.turns)}",
             "Coaching estimates. A short session provides limited coverage. Code was reviewed as text and was not executed."]
    for kind, labels in (
        ("technical", ("Technical accuracy", "Coverage", "Reasoning and trade-offs", "Clarity")),
        ("behavioural", ("Relevance", "Specificity", "Structure", "Reflection")),
    ):
        subset = [t for t in answered if t.question.kind == kind]
        if subset:
            for dimension, label in zip(dimensions, labels):
                average = sum(getattr(t.feedback, dimension).score for t in subset) / len(subset)
                lines.append(f"{label} · {average:.2f}/4 ({len(subset)} scored questions)")
    for number, turn in enumerate(session.turns[:min(session.index + 1, session.budget)], 1):
        lines.extend([f"## {number}. {turn.question.question}", f"Outcome · {turn.outcome}"])
        if turn.confirmed:
            lines.append("Confirmed answer\n\n" + turn.confirmed)
        if turn.feedback:
            feedback = turn.feedback
            lines.extend(["Strengths\n\n" + feedback.correct, "Gaps\n\n" + feedback.missing,
                          "Improved explanation\n\n" + feedback.corrected, evidence_markdown(feedback)])
            for number, prior in enumerate(turn.retries, 1):
                lines.append(f"### Earlier attempt {number}\n\n{turn.previous_answers[number-1]}\n\n{prior.corrected}")
    lines.append("## Prioritised study actions")
    weak = sorted(answered, key=lambda t: sum(getattr(t.feedback, d).score for d in dimensions))
    actions = [f"Review {t.feedback.missing} Then explain the correction aloud without notes." for t in weak[:3]]
    defaults = ["Review the prerequisites of your selected topic and explain one example.",
                "Rehearse your personal contribution with one truthful, specific example.",
                "Practise one failure scenario and explain a trade-off."]
    lines.extend(f"{index+1}. {action}" for index, action in enumerate((actions+defaults)[:3]))
    lines.append("Next practice · Three questions on the weakest topic, followed by one deeper follow-up.")
    return "\n\n".join(lines)
