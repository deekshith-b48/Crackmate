"""Practice uses questions from the reviewed project and skill lessons."""
from core.material import GENERATION_LOCKS, Material, validate_citations
from core.schemas import Feedback


RUBRIC = {
    "accuracy": "Technical accuracy",
    "coverage": "Coverage",
    "reasoning": "Reasoning and trade-offs",
    "clarity": "Clarity",
}
SCALE = "0 absent or wrong · 1 limited · 2 partial · 3 sound with minor gaps · 4 strong"


def review_answer(store, service, record, attempt_id, request, question, answer, progress, *, assistance=None):
    if not answer.strip() or len(answer) > 3500:
        raise ValueError("Enter an answer between 1 and 3,500 characters.")
    lock = GENERATION_LOCKS[hash((record.id, attempt_id)) % len(GENERATION_LOCKS)]
    with lock:
        saved = next((attempt for attempt in store.attempts(record.id) if attempt.id == attempt_id), None)
        if saved:
            return saved.feedback
        context = {
            "focus": request.title,
            "lesson_context": {
                key: value for key, value in request.context.items() if key != "project"
            },
            "question": question.question,
            "example_answer": question.answer,
            "candidate_answer": answer.strip(),
        }
        if request.kind == "project":
            context["lesson_context"]["project"] = {
                key: value for key, value in request.context["project"].items() if key != "reference"
            }
        evidence = Material(store, service).evidence(request)
        context["source_passages"] = evidence
        feedback, _ = service.generate("feedback", context, Feedback,
                                      validate=lambda result: validate_citations(result, evidence, required=False),  # scoring an answer need not cite a source
                                      progress=progress)
        feedback.evidence = evidence
        from core.learning import RUBRIC
        feedback.learning_metadata = {
            "rubric": RUBRIC, "difficulty": request.context.get("level", "unknown"),
            "hint": (assistance or {}).get("hint", False),
            "revealed": (assistance or {}).get("revealed", False),
            "retry": False,
            "independent": not any((assistance or {}).values()),
        }
        store.save_attempt(record, attempt_id, request.title, question.question, answer.strip(), feedback)
        return feedback
