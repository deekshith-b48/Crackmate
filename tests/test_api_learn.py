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
from core.llm import ModelService
from core.material import Material
from core.schemas import ClaimReport, Diagram, Ladder, Pitch, ProjectLesson
from core.storage import Storage

sys.path.insert(0, str(Path(__file__).parent))
from test_material import skill_lesson  # noqa: E402


def project_lesson():
    questions = [{"question": f"Q{n}?", "answer": "An answer.", "hint": "A hint."} for n in range(6)]
    return ProjectLesson(prerequisites=["HTTP"], terms=["API"], explanation="How it works.", example="An example.",
                         project_application="In your project.", questions=questions, follow_ups=questions[:2],
                         exercise="Explain it.", assumptions="(Assumption) a database.")


CLAIMS = ClaimReport(claims=[{"claim": "Cut latency 40%", "source": "API", "kind": "metric", "risk": "high", "why": "w",
                              "probe": "How did you measure it?", "defend": "d", "prepare": "p"}])
PITCH = Pitch(opening="I built an API.", pitch=" ".join(["word"] * 250), key_points=["a", "b", "c"], assumptions="None.")
DIAGRAM = Diagram(diagram='flowchart LR\n  A["Browser"] --> B["API"]', assumptions="(Assumption) DB")
LADDER = Ladder(steps=[{"level": l, "question": f"{l}?", "answer": "a"} for l in ("why", "how", "what_if_it_fails", "how_does_it_scale")])


class LearnApiTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = Settings(api_key="synthetic", database=Path(directory.name) / "t.sqlite3")
        store = Storage(settings.database)
        service = ModelService(settings)
        self.service = service
        self.model = settings.model
        self.core = Core(settings, store, service, Material(store, service))
        self.client = TestClient(create_app(self.core, serve_web=False), base_url="http://127.0.0.1:8000",
                                 headers={"x-crackmate": "1"}, raise_server_exceptions=False)
        self.pid = self.client.post("/api/profiles").json()["id"]
        rev = self.client.get(f"/api/profiles/{self.pid}").json()["revision"]
        added = self.client.post(f"/api/profiles/{self.pid}/projects",
                                 json={"revision": rev, "title": "API", "contribution": "Caching"}).json()
        self.project = added["profile"]["projects"][0]["id"]
        self.base = f"/api/profiles/{self.pid}"

    def stream(self, path, body):
        events = [json.loads(line) for line in self.client.post(self.base + path, json=body).text.splitlines() if line]
        self.assertEqual(events[-1]["type"], "result", events[-1])
        return events[-1]["data"]

    def test_skill_lesson_states_and_shared_cache_across_profiles(self):
        ref = {"kind": "skill", "topic": "Caching", "level": "Basics"}
        groups = self.client.get(self.base + "/lessons/topics").json()["groups"]
        self.assertIn("Caching", [t for g in groups for t in g["topics"]])
        self.assertEqual(self.client.get(self.base + "/lessons", params=ref).json()["status"], "none")
        with patch.object(self.service, "generate", return_value=(skill_lesson(), self.model)) as model:
            made = self.stream("/lessons/generate", ref)
            self.assertEqual(made["status"], "current")
            self.assertTrue(made["fresh"])
            self.assertEqual(made["item"]["questions"][0]["qid"], self.client.get(self.base + "/lessons", params=ref).json()["item"]["questions"][0]["qid"])
            self.assertIn("Concept", [s["label"] for s in made["item"]["sections"]])
            done = self.client.post(self.base + "/lessons/complete", json=ref | {"completed": True}).json()
            self.assertTrue(done["item"]["completed"])
            other = self.client.post("/api/profiles").json()["id"]
            peek = self.client.get(f"/api/profiles/{other}/lessons", params=ref).json()
            self.assertEqual((peek["status"], peek["shared_available"]), ("shared", True))
            loaded = self.client.post(f"/api/profiles/{other}/lessons/generate", json=ref)
            self.assertIn('"type":"result"', loaded.text.replace(" ", ""))
            model.assert_called_once()  # the second profile never called the model

    def test_project_sections_overview_and_generate_all(self):
        with patch.object(self.service, "generate", return_value=(project_lesson(), self.model)):
            rows = self.client.get(self.base + "/lessons/overview", params={"project_id": self.project}).json()
            self.assertEqual([r["status"] for r in rows], ["none"] * 6)
            self.stream("/lessons/generate", {"kind": "project", "project_id": self.project, "section": "Database"})
            rows = self.client.get(self.base + "/lessons/overview", params={"project_id": self.project}).json()
            self.assertEqual([r["status"] for r in rows].count("current"), 1)
            result = self.stream("/lessons/generate-all", {"project_id": self.project})
            self.assertEqual(result, {"done": 5, "failed": []})
        bad = self.client.get(self.base + "/lessons", params={"kind": "project", "project_id": "nope", "section": "Database"})
        self.assertEqual(bad.status_code, 404)

    def test_claims_pitch_diagram_and_ticks(self):
        with patch.object(self.service, "generate", return_value=(CLAIMS, self.model)):
            made = self.stream("/artifacts/claims/run", {})
        self.assertEqual((made["status"], made["ticked"]), ("current", []))
        bad = self.client.put(self.base + "/claims/tick", json={"digest": "wrong", "index": 0, "on": True})
        self.assertEqual(bad.status_code, 400)
        ok = self.client.put(self.base + "/claims/tick", json={"digest": made["digest"], "index": 0, "on": True}).json()
        self.assertEqual(ok["ticked"], [0])
        self.assertEqual(self.client.get(self.base + "/artifacts/claims").json()["ticked"], [0])
        self.assertIn("40%", self.client.get(self.base + "/artifacts/claims/export").text)
        with patch.object(self.service, "generate", return_value=(PITCH, self.model)):
            self.assertEqual(self.stream("/artifacts/pitch/run", {"project_id": self.project})["status"], "current")
        with patch.object(self.service, "generate", return_value=(DIAGRAM, self.model)):
            self.assertEqual(self.stream("/artifacts/diagram/run", {"project_id": self.project})["status"], "current")
        self.assertIn("```mermaid", self.client.get(self.base + "/artifacts/diagram/export", params={"project_id": self.project}).text)
        self.assertEqual(self.client.get(self.base + "/artifacts/pitch").status_code, 404)  # needs a project
        self.assertEqual(self.client.get(self.base + "/artifacts/nope").status_code, 404)

    def test_reviews_and_ladder(self):
        card = {"slot": "skill:Basics:Caching", "question": "What is a cache?", "answer": "Fast storage.", "hint": "h"}
        self.assertEqual(self.client.post(self.base + "/reviews/rate", json=card | {"grade": "Again"}).json()["days"], 0)
        self.assertEqual(self.client.post(self.base + "/reviews/rate", json=card | {"grade": "Bogus"}).status_code, 400)
        self.assertEqual([r["question"] for r in self.client.get(self.base + "/reviews/due").json()], ["What is a cache?"])
        ask = {k: card[k] for k in ("slot", "question", "answer")}
        self.assertEqual(self.client.post(self.base + "/ladder/lookup", json=ask).json(), {"status": "none", "steps": None})
        with patch.object(self.service, "generate", return_value=(LADDER, self.model)):
            built = self.stream("/ladder/build", ask)
        self.assertEqual([s["level"] for s in built["steps"]], ["why", "how", "what_if_it_fails", "how_does_it_scale"])
        self.assertEqual(self.client.post(self.base + "/ladder/lookup", json=ask).json()["status"], "current")

    def test_dashboard_shape(self):
        data = self.client.get(self.base + "/dashboard").json()
        self.assertEqual(data["readiness"]["overall"], None)
        self.assertEqual((data["projects"], data["due_reviews"], data["attempts"]), (1, 0, 0))
        self.assertTrue(data["queue"])
