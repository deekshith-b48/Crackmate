from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sys
import unittest

from fastapi.testclient import TestClient

from api.deps import Core
from api.main import create_app
from core.config import Settings
from core.interview import PlannedQuestion, QuestionPlan
from core.llm import ModelService
from core.material import Material
from core.schemas import Feedback
from core.storage import Storage

sys.path.insert(0, str(Path(__file__).parent))
from test_material import skill_lesson  # noqa: E402

score = lambda n: {"score": n, "reason": f"Reason {n}"}
FEEDBACK = Feedback(accuracy=score(3), coverage=score(2), reasoning=score(3), clarity=score(4), correct="Good start.",
                    missing="Mention failure cases.", corrected="A better answer.", follow_up="What if it fails?")


class PracticeApiTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = Settings(api_key="synthetic", database=Path(directory.name) / "t.sqlite3")
        store = Storage(settings.database)
        self.service = ModelService(settings)
        self.model = settings.model
        self.core = Core(settings, store, self.service, Material(store, self.service))
        self.client = TestClient(create_app(self.core, serve_web=False), base_url="http://127.0.0.1:8000",
                                 headers={"x-crackmate": "1"}, raise_server_exceptions=False)
        self.pid = self.client.post("/api/profiles").json()["id"]
        self.base = f"/api/profiles/{self.pid}"
        patcher = patch.object(self.service, "generate", side_effect=self.fake_model)
        self.generate = patcher.start()
        self.addCleanup(patcher.stop)

    def fake_model(self, kind, context, schema, validate=None, progress=None):
        if kind == "interview_plan":
            n = context["count"]
            plan = QuestionPlan(questions=[PlannedQuestion(question=f"Interview question {i}?", answer="SECRET REFERENCE ANSWER",
                                                           hint="Think about packets.") for i in range(n)])
            return plan, self.model
        if kind == "feedback":
            return FEEDBACK.model_copy(deep=True), self.model
        return skill_lesson(), self.model

    def stream(self, path, body=None):
        response = self.client.post(self.base + path, json=body or {})
        events = [json.loads(line) for line in response.text.splitlines() if line]
        return events[-1]

    def start(self, **extra):
        body = {"mode": "Technical fundamentals", "topic": "Networking", "difficulty": "Basics", "budget": 3, "consent": True} | extra
        last = self.stream("/interviews", body)
        self.assertEqual(last["type"], "result", last)
        return last["data"]

    def test_text_practice_flow(self):
        self.assertEqual(self.client.get(self.base + "/practice/focus").json(), [])
        self.stream("/lessons/generate", {"kind": "skill", "topic": "Networking", "level": "Basics"})
        (focus,) = self.client.get(self.base + "/practice/focus").json()
        self.assertEqual(len(focus["questions"]), 3)
        body = {"slot": focus["slot"], "index": 0, "attempt_id": "attempt-0001", "text": "TCP is reliable.", "hint": True}
        result = self.stream("/practice/answer", body)["data"]
        self.assertEqual([s["label"] for s in result["feedback"]["scores"]][:2], ["Technical accuracy", "Coverage"])
        calls = self.generate.call_count
        self.assertEqual(self.stream("/practice/answer", body)["data"]["feedback"]["correct"], "Good start.")
        self.assertEqual(self.generate.call_count, calls)  # same attempt id: saved feedback, no second model call
        (attempt,) = self.client.get(self.base + "/practice/attempts").json()
        self.assertEqual(attempt["answer"], "TCP is reliable.")
        self.assertEqual(self.stream("/practice/answer", body | {"index": 9, "attempt_id": "attempt-0002"})["type"], "error")

    def test_interview_lifecycle_hides_reference_answer(self):
        self.assertEqual(self.stream("/interviews", {"mode": "Technical fundamentals", "consent": False})["type"], "error")
        self.assertEqual(self.client.get(self.base + "/interviews/options").json()["modes"][0], "Project deep-dive")
        session = self.start()
        sid = session["id"]
        self.assertNotIn("SECRET REFERENCE ANSWER", json.dumps(session))
        self.assertIsNone(session["turn"]["hint"])
        hinted = self.client.post(f"{self.base}/interviews/{sid}/hint").json()
        self.assertEqual(hinted["turn"]["hint"], "Think about packets.")
        self.assertEqual(self.client.post(f"{self.base}/interviews/{sid}/confirm", json={"text": "  "}).status_code, 400)
        confirmed = self.client.post(f"{self.base}/interviews/{sid}/confirm", json={"text": "TCP is reliable."}).json()
        self.assertEqual(confirmed["state"], "transcript review")
        done = self.stream(f"/interviews/{sid}/evaluate")["data"]
        self.assertEqual(done["state"], "feedback ready")
        self.assertEqual(done["turn"]["feedback"]["follow_up"], "What if it fails?")
        nxt = self.client.post(f"{self.base}/interviews/{sid}/next", json={"follow": True}).json()
        self.assertEqual((nxt["index"], nxt["turn"]["depth"]), (1, 1))  # the adaptive follow-up replaced question 2
        self.assertEqual(nxt["turn"]["question"], "What if it fails?")
        self.client.post(f"{self.base}/interviews/{sid}/skip")
        paused = self.client.post(f"{self.base}/interviews/{sid}/pause").json()
        self.assertEqual(paused["state"], "paused")
        self.assertEqual(self.client.post(f"{self.base}/interviews/{sid}/resume").json()["state"], "question ready")
        ended = self.client.post(f"{self.base}/interviews/{sid}/end").json()
        self.assertEqual((ended["state"], ended["turn"]), ("completed", None))
        report = self.client.get(f"{self.base}/interviews/{sid}/report").json()
        self.assertEqual((report["scored"], report["skipped"]), (1, 1))
        self.assertIn("Mock interview report", report["markdown"])
        self.assertEqual(report["study_next"][0]["href"], "/learn/skills/?topic=Networking&level=Basics")
        self.assertEqual(self.client.delete(f"{self.base}/interviews/{sid}").status_code, 400)
        self.assertEqual(self.client.delete(f"{self.base}/interviews/{sid}", params={"confirm": "true"}).status_code, 200)
        self.assertEqual(self.client.get(f"{self.base}/interviews/{sid}").status_code, 404)

    def test_simulation_mode_defers_feedback_until_coach_switch(self):
        sid = self.start(coach=False)["id"]
        self.client.post(f"{self.base}/interviews/{sid}/confirm", json={"text": "An answer."})
        turn = self.stream(f"/interviews/{sid}/evaluate")["data"]["turn"]
        self.assertEqual((turn["has_feedback"], turn["feedback"]), (True, None))
        revealed = self.client.post(f"{self.base}/interviews/{sid}/coach").json()
        self.assertIsNotNone(revealed["turn"]["feedback"])
        retried = self.client.post(f"{self.base}/interviews/{sid}/retry").json()
        self.assertEqual((retried["turn"]["retries"], retried["state"]), (1, "question ready"))

    def test_voice_transcription_is_never_repeated(self):
        sid = self.start()["id"]
        wav = b"RIFF-not-really-audio"
        with patch("api.services.interviews.transcribe", return_value="My spoken answer") as transcribe:
            first = self.client.post(f"{self.base}/interviews/{sid}/transcribe", files={"file": ("a.wav", wav, "audio/wav")}).json()
            again = self.client.post(f"{self.base}/interviews/{sid}/transcribe", files={"file": ("a.wav", wav, "audio/wav")}).json()
        transcribe.assert_called_once()
        self.assertEqual((first["state"], first["turn"]["original"]), ("transcript review", "My spoken answer"))
        self.assertEqual(again["turn"]["original"], "My spoken answer")

    def test_claims_are_offered_only_when_a_claim_check_exists(self):
        self.assertEqual(self.client.get(self.base + "/interviews/options").json()["open_claims"], 0)
