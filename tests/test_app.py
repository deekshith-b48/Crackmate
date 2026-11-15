"""Exercise Streamlit through its normal controls with a temporary DB and synthetic responses."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core.config import Settings
from core.llm import ModelError
from core.schemas import Feedback, ProfileDraft, ProjectLesson, PlanDraft
from core.storage import Storage
from test_material import skill_lesson
from test_resume import pdf_bytes


def element(elements, label):
    return next(widget for widget in elements if widget.label == label)


class AppTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.settings = Settings(api_key="synthetic", database=Path(directory.name) / "test.sqlite3")
        self.store = Storage(self.settings.database)
        settings = patch("core.config.Settings.load", return_value=self.settings)
        settings.start()
        self.addCleanup(settings.stop)
        self.calls = []
        provider = patch("core.llm.ModelService.generate", side_effect=self.synthetic)
        self.provider = provider.start()
        self.addCleanup(provider.stop)
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=8).run()
        self.assert_no_errors()

    def synthetic(self, kind, context, schema, *, validate=None, **kwargs):
        self.calls.append((kind, context))
        question = {"question": "How do you handle retries?", "answer": "Retry a transient failure.", "hint": "Classify the failure first."}
        score = {"score": 3, "reason": "Specific to transient errors."}
        if kind == "profile":
            result = ProfileDraft(projects=[{"title": "Task API", "contribution": "Built routes"}])
        elif kind == "project":
            result = ProjectLesson(
                prerequisites=["Requests"], terms=["Idempotency"], explanation="A request should be repeatable.",
                example="Repeat a GET.", project_application="Use request IDs.", questions=[question] * 6,
                follow_ups=[question] * 2, exercise="Design a retry policy.", assumptions="Storage unknown."
            )
        elif kind == "skill":
            result = skill_lesson()
        elif kind == "feedback":
            result = Feedback(accuracy=score, coverage=score, reasoning=score, clarity=score,
                              correct="Retry with limits.", missing="Backoff.", corrected="Retry with backoff.",
                              follow_up="What about jitter?")
        else:
            resource = next(iter(context["resources"]))
            result = PlanDraft(blocks=[
                {"duration_minutes": minutes, "topic": "Task API", "reason": "Resume project",
                 "outcome": "Explain a request in two minutes.", "reference": resource}
                for minutes in context["study_windows_minutes"]
            ])
        if validate:
            validate(result)
        return result, self.settings.model

    def assert_no_errors(self):
        self.assertEqual([exc.message for exc in self.app.exception], [])
        self.assertEqual([err.value for err in self.app.error], [])

    def page(self, name):
        element(self.app.radio, "Go to").set_value(name).run()
        self.assert_no_errors()

    def button(self, name):
        element(self.app.button, name).click().run()
        self.assert_no_errors()

    def test_resume_to_practice_plan_export_and_deletion(self):
        preview = "Python developer. Built routes for a task API."
        element(self.app.text_area, "Editable resume preview").set_value(preview)
        element(self.app.checkbox, "Send the reviewed resume text to Groq").set_value(True)
        self.button("Extract profile")
        self.assertEqual(self.calls[0], ("profile", {"reviewed_resume": preview}))
        record = self.store.profiles()[0]
        element(self.app.text_area, "Your contribution").set_value("Implemented caching")
        self.button("Save project")
        self.page("Projects")
        self.button("Generate lesson")
        self.assertEqual(self.calls[-1][1]["project"]["contribution"], "Implemented caching")
        self.app.run()
        self.button("Load saved lesson")
        self.assertEqual([kind for kind, _ in self.calls].count("project"), 1)
        self.button("Mark complete")
        self.assertTrue(self.store.completed(record.id, self.store.items(record.id)[0]))
        self.page("Skills")
        element(self.app.selectbox, "Topic").set_value("Networking").run()
        self.button("Generate lesson")
        self.page("Practice")
        element(self.app.text_area, "Your answer").set_value("Retry transient errors with backoff.")
        self.button("Get feedback")
        self.assertEqual(len(self.store.attempts(record.id)), 1)
        self.button("Next question")
        self.page("Preparation plan")
        self.button("Build plan")
        self.assertEqual(self.calls[-1][0], "plan")
        self.assertEqual(sum(self.calls[-1][1]["study_windows_minutes"]), 120)
        self.assertTrue(self.app.get("download_button"))
        self.button("Build plan")
        self.assertEqual([kind for kind, _ in self.calls].count("plan"), 1)
        self.button("Open relevant lesson")
        self.assertEqual(element(self.app.radio, "Go to").value, "Projects")
        self.page("Resume and profile")
        self.assertTrue(element(self.app.button, "Delete profile").disabled)
        element(self.app.checkbox, "Permanently delete this profile and its local data").set_value(True).run()
        self.button("Delete profile")
        self.assertEqual(self.store.profiles(), [])
        self.assertEqual(self.store.items(record.id), [])
        self.assertEqual(self.store.attempts(record.id), [])

    def test_pdf_and_latex_uploads_use_the_editable_preview(self):
        element(self.app.radio, "Resume source").set_value("Upload PDF or LaTeX").run()
        for filename, data, expected in (
            ("synthetic.pdf", pdf_bytes("Built an API"), "Built an API"),
            ("synthetic.tex", b"Worked on caching", "Worked on caching"),
        ):
            element(self.app.file_uploader, "Resume file").set_value((filename, data, "application/octet-stream")).run()
            self.button("Read file into preview")
            self.assertEqual(element(self.app.text_area, "Editable resume preview").value, expected)
        draft = "Worked on caching, with contact details removed."
        element(self.app.text_area, "Editable resume preview").set_value(draft)
        element(self.app.checkbox, "Send the reviewed resume text to Groq").set_value(True)
        self.button("Extract profile")
        self.assertEqual(self.calls[0], ("profile", {"reviewed_resume": draft}))

    def test_creating_second_profile_selects_it_and_keeps_the_first(self):
        self.button("Start with a blank profile")
        original = self.app.session_state["active_profile"]
        self.button("Start with a blank profile")
        self.assertNotEqual(self.app.session_state["active_profile"], original)
        self.assertEqual(len(self.store.profiles()), 2)

    def test_failed_extraction_keeps_edited_resume(self):
        self.provider.side_effect = ModelError("Groq is unavailable.")
        draft = "Edited synthetic resume"
        element(self.app.text_area, "Editable resume preview").set_value(draft)
        element(self.app.checkbox, "Send the reviewed resume text to Groq").set_value(True)
        element(self.app.button, "Extract profile").click().run()
        self.assertEqual(element(self.app.text_area, "Editable resume preview").value, draft)
        self.assertEqual(self.store.profiles(), [])
        self.assertIn("Groq is unavailable.", [error.value for error in self.app.error])
