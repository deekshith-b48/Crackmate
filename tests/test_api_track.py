from datetime import datetime, timedelta
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
from core.schemas import PlanDraft, StudyBlock
from core.storage import Storage

sys.path.insert(0, str(Path(__file__).parent))
from test_material import skill_lesson  # noqa: E402


class TrackApiTests(unittest.TestCase):
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
        if kind == "plan":
            blocks = [StudyBlock(duration_minutes=m, topic=f"Topic {i}", reason="Because it matters.", outcome="Explain it.", reference=None)
                      for i, m in enumerate(context["study_windows_minutes"])]
            return PlanDraft(blocks=blocks), self.model
        return skill_lesson(), self.model

    def stream(self, path, body):
        events = [json.loads(l) for l in self.client.post(self.base + path, json=body).text.splitlines() if l]
        return events[-1]

    def test_plan_build_reuse_and_export(self):
        self.assertEqual(self.client.get(self.base + "/plan").json()["status"], "none")
        interview = (datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(timespec="minutes")
        body = {"interview": interview, "hours": 2, "weak_areas": "Caching"}
        made = self.stream("/plan", body)
        self.assertEqual(made["type"], "result", made)
        plan = made["data"]
        self.assertEqual(plan["status"], "current")
        self.assertEqual(sum(b["minutes"] for b in plan["plan"]["blocks"]), 120)
        calls = self.generate.call_count
        self.assertEqual(self.stream("/plan", body)["data"]["status"], "current")
        self.assertEqual(self.generate.call_count, calls)  # identical inputs reuse the saved plan
        self.stream("/plan", body | {"regenerate": True})
        self.assertEqual(self.generate.call_count, calls + 1)
        self.assertIn("Preparation plan", self.client.get(self.base + "/plan/export").text)
        past = (datetime.now() - timedelta(hours=1)).isoformat(timespec="minutes")
        self.assertEqual(self.stream("/plan", {"interview": past, "hours": 2})["type"], "error")

    def test_queue_topics_and_settings(self):
        progress = self.client.get(self.base + "/learning/progress").json()
        self.assertEqual((progress["readiness"]["overall"], len(progress["topics"])), (None, 9))
        tid = progress["topics"][0]["id"]
        queue = self.client.get(self.base + "/learning/queue", params={"minutes": 60}).json()
        self.assertTrue(queue)
        first = queue[0]["topic"]
        self.assertEqual(self.client.post(f"{self.base}/learning/queue/{first}", json={"action": "dismiss"}).status_code, 200)
        self.assertNotIn(first, [q["topic"] for q in self.client.get(self.base + "/learning/queue", params={"minutes": 60}).json()])
        self.client.post(self.base + "/learning/queue/restore")
        self.assertIn(first, [q["topic"] for q in self.client.get(self.base + "/learning/queue", params={"minutes": 60}).json()])
        self.assertEqual(self.client.post(f"{self.base}/learning/queue/{first}", json={"action": "nope"}).status_code, 400)
        detail = self.client.post(f"{self.base}/learning/topics/{tid}", json={"action": "review_tomorrow"}).json()
        self.assertTrue(detail["due"] is None or isinstance(detail["due"], str))
        self.assertEqual(self.client.post(f"{self.base}/learning/topics/nope", json={"action": "reset_schedule"}).status_code, 404)
        settings = self.client.get(self.base + "/learning/settings").json()["settings"]
        good = settings | {"timezone": "Asia/Kolkata", "daily_minutes": 90}
        self.assertEqual(self.client.put(self.base + "/learning/settings", json=good).json()["settings"]["daily_minutes"], 90)
        self.assertEqual(self.client.put(self.base + "/learning/settings", json=good | {"timezone": "Mars/Base"}).status_code, 400)
        self.assertEqual(self.client.put(self.base + "/learning/settings", json=good | {"intervals": [7, 3]}).status_code, 400)

    def test_adaptive_plan_proposal_is_server_side(self):
        proposal = self.client.post(self.base + "/learning/propose").json()
        self.assertTrue(proposal["blocks"])
        self.assertEqual(self.client.post(self.base + "/learning/apply", json={"id": "forged"}).status_code, 400)
        blocks = self.client.post(self.base + "/learning/apply", json={"id": proposal["id"]}).json()
        self.assertEqual(len(blocks), len(proposal["blocks"]))
        self.assertEqual(self.client.post(self.base + "/learning/apply", json={"id": proposal["id"]}).status_code, 400)  # one use
        updated = self.client.put(f"{self.base}/learning/plan/{blocks[0]['id']}", json={"completed": True, "pinned": True}).json()
        self.assertEqual((updated[0]["completed"], updated[0]["pinned"]), (True, True))

    def test_knowledge_library_and_company(self):
        client = self.client
        self.assertEqual(client.get("/api/knowledge/sources").json(), [])
        text = "A load balancer spreads requests across servers so none is overloaded. " * 5
        self.assertEqual(client.post("/api/knowledge/import", json={"title": "LB notes", "text": text, "license": "MIT"}).json()["result"], "Imported")
        (source,) = client.get("/api/knowledge/sources").json()
        self.assertEqual((source["title"], source["license"]), ("LB notes", "MIT"))
        self.assertTrue(client.get("/api/knowledge/search", params={"q": "load balancer"}).json())
        self.assertEqual(client.get("/api/knowledge/search", params={"q": " "}).json(), [])
        self.assertEqual(client.post(f"/api/knowledge/{source['id']}/refresh").status_code, 404)  # only web sources refresh
        up = client.post("/api/knowledge/import-file", files={"file": ("notes.txt", text.encode(), "text/plain")}, data={"title": "From file"})
        self.assertEqual(up.status_code, 200, up.text)
        self.assertEqual(len(client.get("/api/knowledge/sources").json()), 2)
        self.assertEqual(client.delete(f"/api/knowledge/{source['id']}").status_code, 200)
        with patch("api.services.knowledge.company.companies", return_value=["Acme"]), patch(
                "api.services.knowledge.company.problems",
                return_value=[{"Title": "Two Sum", "Difficulty": "Easy", "Frequency": 90.0, "Topics": "Array", "Link": "https://leetcode.com/problems/two-sum"}]):
            self.assertEqual(client.get("/api/company/list").json(), {"companies": ["Acme"]})
            rows = client.get("/api/company/problems", params={"company_name": "Acme", "levels": "Easy"}).json()
            self.assertEqual((rows["rows"][0]["Title"], rows["focus"]), ("Two Sum", [["Array", 1]]))
            self.assertEqual(client.get("/api/company/problems", params={"company_name": "Acme", "window": "Never"}).status_code, 400)
        self.assertIn("Array", client.get("/api/company/fallback").json()["topics"])

    def test_exports(self):
        self.assertEqual(self.client.get(self.base + "/export/lesson", params={"kind": "skill", "topic": "Networking", "level": "Basics"}).status_code, 400)
        self.stream("/lessons/generate", {"kind": "skill", "topic": "Networking", "level": "Basics"})
        lesson = self.client.get(self.base + "/export/lesson", params={"kind": "skill", "topic": "Networking", "level": "Basics"})
        self.assertIn("Concept", lesson.text)
        self.assertIn("attachment", lesson.headers["content-disposition"])
        self.assertIn("CrackMate preparation", self.client.get(self.base + "/export/all").text)
        self.assertIn("Learning progress", self.client.get(self.base + "/export/learning").text)
