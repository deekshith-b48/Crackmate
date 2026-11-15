from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.export import markdown
from core.planning import Plan, PlanInput, build_windows, check_plan
from core.schemas import Feedback, PlanDraft, Profile
from core.storage import Storage


class PracticePlanExportTests(unittest.TestCase):
    def test_windows_fit_budget_and_preserve_overnight(self):
        start = datetime(2026, 11, 14, 22, 0)
        end = datetime(2026, 11, 15, 9, 5)
        blocks = build_windows(start, end, 150)
        self.assertEqual(sum(block.minutes for block in blocks), 150)
        for block in blocks:
            self.assertGreaterEqual(block.start.hour, 7)
            self.assertLessEqual(block.end.hour, 23)
            self.assertLess(block.end, end)
        plan_input = PlanInput(start=start, interview=end, budget=150, weak_areas="", role_context="")
        with self.assertRaisesRegex(ValueError, "block"):
            check_plan(PlanDraft(blocks=[]), plan_input, blocks, {})

    def test_export_keeps_interview_date_and_time(self):
        start = datetime(2026, 11, 14, 8, 0)
        interview = datetime(2026, 11, 14, 10, 0)
        inputs = PlanInput(start=start, interview=interview, budget=30, weak_areas="", role_context="")
        windows = build_windows(start, interview, 30)
        plan = Plan(inputs=inputs, windows=windows, links={}, blocks=[
            {"duration_minutes": 30, "topic": "Networking", "reason": "Role asks for TCP", "outcome": "Explain DNS"}
        ])
        self.assertIn("2026-11-14 10:00", markdown("Plan", plan))

    def test_attempts_are_isolated_and_cascade_on_delete(self):
        with TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "test.sqlite3")
            a, b = store.create(Profile()), store.create(Profile())
            score = {"score": 2, "reason": "Partial reasoning"}
            feedback = Feedback(
                accuracy=score, coverage=score, reasoning=score, clarity=score,
                correct="Identified TCP.", missing="Connection lifecycle.",
                corrected="TCP uses a handshake.", follow_up="What is the third step?"
            )
            for _ in range(2):
                store.save_attempt(a, "attempt-id", "Networking", "Explain TCP", "My answer", feedback)
            self.assertEqual(len(store.attempts(a.id)), 1)
            self.assertEqual(store.attempts(b.id), [])
            store.delete(a.id)
            self.assertEqual(store.attempts(a.id), [])

    def test_export_preserves_questions_code_and_strips_contact(self):
        from test_material import skill_lesson
        from core.schemas import CodingExample
        lesson = skill_lesson()
        lesson.coding = CodingExample(problem="Count", approach="Map", solution="counts = {}",
                                      walkthrough="Loop", edge_cases="Empty list", complexity="O(n)")
        result = markdown("Example candidate@example.test", lesson)
        self.assertIn("Question 0?", result)
        self.assertIn("~~~python\ncounts = {}\n~~~", result)
        self.assertNotIn("candidate@example.test", result)
