"""Shared Streamlit actions and lesson display."""
import re
import sqlite3

from pydantic import ValidationError
import streamlit as st

from core.export import NOTICE, clean, item_markdown, lesson_sections, parse_item
from core.llm import ModelError
from core.schemas import ProjectLesson
from core.storage import StorageError


class App:
    def __init__(self, settings, store, service, material, record):
        self.settings = settings
        self.store = store
        self.service = service
        self.material = material
        self.record = record

    @property
    def profile(self):
        return self.record.profile

    def save(self, profile):
        if self.action(lambda _: self.store.save(self.record, profile)):
            st.session_state["notice"] = "Profile changes saved."
            st.rerun()

    def action(self, run, label=None):
        status = st.status(label) if label else None
        try:
            result = run(lambda text: status.update(label=text) if status else None)
        except ValidationError:
            error = "Some fields are incomplete or exceed their limits. Check your entries and try again."
        except sqlite3.Error:
            error = "CrackMate could not read or save local data. Check disk permissions and try again."
        except (ModelError, StorageError, ValueError) as exc:
            error = str(exc)
        else:
            if status:
                status.update(label="Saved", state="complete")
            return result
        if status:
            status.update(label="Action needs attention", state="error")
        st.error(error)
        return None


def safe_markdown(text):
    # Model content should never make the browser fetch remote images.
    text = re.sub(r"!\[([^\]]*)\]", r"[\1]", text)
    st.markdown(text)


def download(label, content, name, key):
    st.download_button(label, content, file_name=name, mime="text/markdown", key=key, on_click="ignore")


def lesson_display(lesson, app=None, slot=None):
    from core.export import evidence_markdown
    safe_markdown(evidence_markdown(lesson))
    with st.expander("Retrieved evidence"):
        for passage in lesson.evidence:
            st.text(passage["title"] + " · " + passage["location"])
            st.text(passage["text"])
    for label, body in lesson_sections(lesson):
        st.markdown(f"#### {label}")
        safe_markdown(body)
    for label, questions in (
        ("Practice questions", lesson.questions),
        ("Deeper follow-ups", getattr(lesson, "follow_ups", [])),
    ):
        if questions:
            st.markdown(f"#### {label}")
            for index, question in enumerate(questions):
                if app:
                    from ui.cards import question_card
                    question_card(app, slot, question.question, question.answer, question.hint, index, len(questions), label)
                else:
                    with st.expander(f"{index + 1}. {question.question}"):
                        safe_markdown(question.answer)
    st.markdown("#### Self-check")
    safe_markdown(lesson.exercise)
    if isinstance(lesson, ProjectLesson):
        with st.expander("Assumptions and missing information", expanded=True):
            safe_markdown(lesson.assumptions)


def generator(app, request, tailor_button=False):
    record = app.record
    item = app.store.item(record.id, request.slot)
    current = app.material.current(record, request, item)
    shared = not current and app.material.shared_body(request) is not None
    label = "Load saved lesson" if current else "Load shared lesson (instant)" if shared else "Generate lesson"
    generate, redo, tailor = st.columns(3)
    start = generate.button(
        label, type="primary", key=f"generate:{request.slot}",
        disabled=not current and not shared and not app.settings.api_key,
    )
    regenerate = bool(item) and redo.button(
        "Regenerate lesson", key=f"regenerate:{request.slot}", disabled=not app.settings.api_key
    )
    personal = bool(item) and tailor_button and tailor.button(
        "Tailor to my resume", key=f"tailor:{request.slot}", disabled=not app.settings.api_key,
        help="Rewrites the lesson using your stack and target role. Slower, and kept private to this profile.")
    fresh = False
    if start or regenerate or personal:
        result = app.action(
            lambda progress: app.material.generate(
                record, request, regenerate=regenerate or personal, tailor=personal, progress=progress),
            None if start and (current or shared) else "Generating and checking lesson…",
        )
        if result:
            item, fresh = result
            current = True
    if not item:
        st.info("This lesson is ready to generate when you need it.")
        return

    if not current:
        st.warning("Outdated · The saved lesson uses earlier inputs or model settings.")
    else:
        st.caption("Newly generated and saved" if fresh else f"Saved lesson · {item.model}")
    st.subheader(clean(item.title))
    if current:
        done = app.store.completed(record.id, item)
        if st.button("Mark for review" if done else "Mark complete", key=f"done:{request.slot}"):
            def mark(_):
                app.store.mark_completed(record, item, not done)
                return True

            if app.action(mark):
                st.rerun()
        if done:
            st.caption("Completed")
    lesson_display(parse_item(item), app, request.slot)
    download("Download lesson", NOTICE + "\n\n" + item_markdown(item, outdated=not current),
             "crackmate-lesson.md", f"export:{request.slot}")
