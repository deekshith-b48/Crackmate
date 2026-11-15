"""Ask CrackMate: retrieve cited sources, then stream an answer that may use only them."""
from core.ask import prompt
from core.ask.index import AskIndex
from core.ask.search import hybrid
from core.knowledge import Library


def answer(core, record, question, history, emit):
    sources = hybrid(core, record, question)
    emit({"type": "sources", "data": sources})
    if not sources:  # nothing relevant: say so without spending a model call
        emit({"type": "token", "text": prompt.NOTHING})
    else:
        system, user = prompt.build(question, sources, history)
        for chunk in core.service.stream(system, user, feature="ask"):
            emit({"type": "token", "text": chunk})
    emit({"type": "done"})


def status(core, record):
    index = AskIndex(core.store)
    changed = index.refresh(core, record)
    stats = index.stats(record.id)
    return {"indexed": stats, "passages": sum(stats.values()), "just_indexed": changed,
            "knowledge_sources": len(Library(core.store).sources()),
            "suggestions": [f"What are the hardest parts of {p.title}?" for p in record.profile.projects[:2]]
                           + ["Explain how caching works and where I could use it.", "What would an interviewer ask about my database choices?"]}
