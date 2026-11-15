"""Markdown exports omit raw resumes, contacts, prompts and practice transcripts."""
import re

from core.material import SECTIONS
from core.planning import Plan
from core.schemas import ProjectLesson, SkillLesson


NOTICE = "Generated practice material. Content has not been checked against live web sources."
CONTACT = re.compile(
    r"[\w.+%-]+@[\w.-]+\.[a-z]{2,}|(?<!\w)\+?\d[\d(). -]{7,}\d(?!\w)", re.IGNORECASE
)


def clean(text):
    def redact(match):
        token = match.group()
        if "@" in token or sum(character.isdigit() for character in token) >= 10:
            return "[contact removed]"
        return token

    return CONTACT.sub(redact, text)


def parse_item(item):
    schema = {"project": ProjectLesson, "skill": SkillLesson, "plan": Plan}[item.kind]
    return schema.model_validate_json(item.body)


def bullets(values):
    return "\n".join(f"- {value}" for value in values)


def code_block(solution):
    runs = re.findall(r"~+", solution)
    fence = "~" * max(3, 1 + max(map(len, runs), default=0))
    return f"{fence}python\n{solution}\n{fence}"


def lesson_sections(lesson):
    yield "Prerequisites", bullets(lesson.prerequisites)
    if isinstance(lesson, ProjectLesson):
        yield "Important terms", bullets(lesson.terms)
    yield "Concept", lesson.explanation
    yield "Worked example", lesson.example
    if isinstance(lesson, ProjectLesson):
        yield "Application to this project", lesson.project_application
    else:
        yield "Common mistakes", bullets(lesson.mistakes)
        if lesson.coding:
            coding = lesson.coding
            yield "Coding exercise", (
                f"**Problem**\n\n{coding.problem}\n\n**Approach**\n\n{coding.approach}"
                f"\n\n{code_block(coding.solution)}\n\n**Walkthrough**\n\n{coding.walkthrough}"
                f"\n\n**Edge cases**\n\n{coding.edge_cases}\n\n**Complexity and assumptions**\n\n{coding.complexity}"
            )


def markdown(title, lesson):
    lines = [f"## {clean(title)}"]
    if isinstance(lesson, Plan):
        total = sum(block.duration_minutes for block in lesson.blocks)
        lines += [
            f"Interview (local time) · {lesson.inputs.interview:%Y-%m-%d %H:%M}",
            f"Study time · {total} min out of {lesson.inputs.budget} min",
            "Ten-minute breaks between nearby blocks. Overnight sleep reserved from 23:00 to 07:00.",
        ]
        for index, (window, block) in enumerate(zip(lesson.windows, lesson.blocks, strict=True), 1):
            lines += [
                f"### {index}. {clean(block.topic)}",
                f"{window.start:%a %d %b %H:%M}–{window.end:%H:%M} · {block.duration_minutes} min",
                f"**Reason**\n\n{clean(block.reason)}", f"**Outcome**\n\n{clean(block.outcome)}",
            ]
        return "\n\n".join(lines)
    for label, body in lesson_sections(lesson):
        lines += [f"### {label}", body]
    lines.append("### Practice questions")
    for index, question in enumerate(lesson.questions, 1):
        lines += [f"#### {index}. {question.question}", question.answer]
    if isinstance(lesson, ProjectLesson):
        lines.append("### Deeper follow-ups")
        for question in lesson.follow_ups:
            lines += [f"#### {question.question}", question.answer]
    lines += ["### Self-check", lesson.exercise]
    if isinstance(lesson, ProjectLesson):
        lines += ["### Assumptions and missing information", lesson.assumptions]
    return clean("\n\n".join(lines)) + evidence_markdown(lesson)


def item_markdown(item, *, outdated=False):
    prefix = "**Outdated.** Review the current profile before using this material.\n\n" if outdated else ""
    return prefix + markdown(item.title, parse_item(item))


def project_markdown(project, items, is_current):
    by_slot = {item.slot: item for item in items}
    parts = [f"# {clean(project.title)}", NOTICE]
    for section in SECTIONS:
        item = by_slot.get(f"project:{project.id}:{section}")
        parts.append(item_markdown(item, outdated=not is_current(item)) if item else f"## {section}\n\nIncomplete.")
    return "\n\n".join(parts) + "\n"


def all_markdown(profile, items, is_current):
    parts = ["# CrackMate preparation", NOTICE]
    for project in profile.projects:
        parts.append(project_markdown(project, items, is_current))
    skills = [item for item in items if item.kind == "skill"]
    parts.extend(item_markdown(item, outdated=not is_current(item)) for item in reversed(skills))
    if not skills:
        parts.append("## Skills\n\nIncomplete. No saved skill lessons.")
    plan = next((item for item in items if item.kind == "plan"), None)
    parts.append(item_markdown(plan, outdated=not is_current(plan)) if plan else "## Preparation plan\n\nIncomplete.")
    return "\n\n".join(parts) + "\n"



def evidence_markdown(result):
    if not result.evidence:
        return "\n\nEvidence coverage is unavailable. Generated from general model knowledge."
    if not result.citations:  # sources were retrieved, but the model tied no claim to them
        return "\n\n### Sources and evidence\n\nNo claim here is tied to a source passage, so treat this as general model knowledge. The passages below were retrieved for context only."
    lines = ["\n\n### Sources and evidence", "Partially supported. Citation validation confirms passage identity, not claim correctness."]
    for citation in result.citations:
        passage = next((p for p in result.evidence if p["id"] == citation.passage_id), None)
        if passage:
            lines.append(f"- {citation.claim} — {passage['title']} ({passage['location']}), "
                         f"retrieved {passage['retrieved']}. Passage {passage['id']}. Reuse terms {passage['license']}.")
    return "\n\n".join(lines)


def claims_markdown(report, defended=()):
    lines = ["# Resume claim check", NOTICE, "Questions are most likely, never guaranteed."]
    for index, claim in enumerate(report.claims):
        mark = "defended" if index in defended else "not yet defended"
        lines += [f"## {claim.claim} ({claim.risk} risk, {mark})", f"*{claim.source}* · {claim.why}",
                  f"**Likely question:** {claim.probe}", f"**Be ready to explain:** {claim.defend}",
                  f"**Prepare:** {claim.prepare}"]
    return clean("\n\n".join(lines)) + "\n"


def pitch_markdown(title, pitch):
    words = len(pitch.pitch.split())
    points = bullets(pitch.key_points)
    return clean(f"# {title}\n\n{NOTICE}\n\n{pitch.pitch}\n\n_About {words} words, roughly {max(1, round(words / 140))} minutes spoken._"
                 f"\n\n## Be ready to expand on\n\n{points}\n\n## Assumptions\n\n{pitch.assumptions}") + "\n"


def diagram_markdown(title, diagram):
    return (f"# {clean(title)}\n\n{NOTICE}\n\n```mermaid\n{diagram.diagram}\n```\n\n"
            f"## Assumptions\n\n{clean(diagram.assumptions)}\n")


def decisions_markdown(title, found):
    lines = [f"# {clean(title)}", NOTICE, "Each decision cites evidence from the repository. Confidence says how well the evidence supports it."]
    for d in found.decisions:
        refs = ", ".join(f"{e.kind} `{e.ref}`" for e in d.evidence)
        lines += [f"## {d.title} ({d.confidence} confidence)", f"**Decision:** {d.decision}", f"**Evidence:** {refs}",
                  f"**Alternatives:** {', '.join(d.alternatives) or 'none noted'}", f"**Likely question:** {d.tradeoff_question}",
                  f"**Answer:** {d.answer}"] + ([f"**Assumption:** {d.assumption}"] if d.assumption else [])
    return clean("\n\n".join(lines)) + "\n"
