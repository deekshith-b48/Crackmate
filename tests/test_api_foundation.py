from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from fastapi.testclient import TestClient

from api.deps import Core
from api.main import create_app
from api.streaming import stream_job
from core.config import Settings
from core.llm import ModelService
from core.material import Material
from core.schemas import Profile, Project
from core.storage import Storage

KEY = "gsk_SECRET_FOR_TEST"
OK = {"host": "127.0.0.1:8000"}


def make_core(directory):
    settings = Settings(api_key=KEY, database=Path(directory) / "t.sqlite3")
    store = Storage(settings.database)
    service = ModelService(settings)
    return Core(settings, store, service, Material(store, service))


class FoundationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.core = make_core(directory.name)
        self.app = create_app(self.core, serve_web=False)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8000")

        @self.app.post("/api/echo")
        def echo():
            return {"ok": True}

        @self.app.get("/api/job")
        def job(fail: str = ""):
            def work(progress):
                progress("one")
                progress("two")
                if fail == "friendly":
                    raise ValueError("Pick a project first.")
                if fail == "secret":
                    raise RuntimeError("password=hunter2")
                return {"done": True}
            return stream_job(work)

    def test_status_never_exposes_the_key(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["has_key"])
        self.assertNotIn(KEY, response.text)
        self.assertNotIn("gsk_", response.text)

    def test_rebinding_host_is_rejected(self):
        self.assertEqual(self.client.get("/api/status", headers={"host": "evil.example.com"}).status_code, 403)
        self.assertEqual(self.client.get("/api/status", headers={"host": "localhost:3000"}).status_code, 200)

    def test_writes_need_header_and_a_local_origin(self):
        self.assertEqual(self.client.post("/api/echo").status_code, 403)
        self.assertEqual(self.client.post("/api/echo", headers={"x-crackmate": "1", "origin": "https://evil.example.com"}).status_code, 403)
        self.assertEqual(self.client.post("/api/echo", headers={"x-crackmate": "1", "origin": "http://127.0.0.1:3000"}).status_code, 200)
        self.assertEqual(self.client.post("/api/echo", headers={"x-crackmate": "1"}).status_code, 200)

    def test_cors_allows_only_local_origins(self):
        good = self.client.options("/api/echo", headers={"origin": "http://127.0.0.1:3000", "access-control-request-method": "POST"})
        self.assertEqual(good.headers.get("access-control-allow-origin"), "http://127.0.0.1:3000")
        bad = self.client.options("/api/echo", headers={"origin": "https://evil.example.com", "access-control-request-method": "POST"})
        self.assertIsNone(bad.headers.get("access-control-allow-origin"))

    def events(self, query=""):
        return [json.loads(line) for line in self.client.get("/api/job" + query).text.splitlines() if line]

    def test_stream_steps_then_result(self):
        self.assertEqual([e["type"] for e in self.events()], ["step", "step", "result"])
        self.assertEqual(self.events()[-1]["data"], {"done": True})

    def test_stream_errors_are_friendly_and_never_leak(self):
        self.assertEqual(self.events("?fail=friendly")[-1], {"type": "error", "message": "Pick a project first."})
        leaked = self.events("?fail=secret")[-1]
        self.assertEqual(leaked["type"], "error")
        self.assertNotIn("hunter2", leaked["message"])

    def test_profiles_list(self):
        self.core.store.create(Profile(name="Asha", role="Backend", projects=[Project(title="API")]))
        (row,) = self.client.get("/api/profiles").json()
        self.assertEqual((row["name"], row["role"], row["projects"]), ("Asha", "Backend", 1))


class ErrorMessageTests(unittest.TestCase):
    def test_rate_limit_message_includes_wait_time(self):
        from api.errors import describe
        from core.llm import ModelError
        status, message = describe(ModelError("Groq is rate limiting requests.", try_next=True, retry_after=757))
        self.assertEqual(status, 502)
        self.assertIn("about 13 minute", message)
        self.assertNotIn("minute", describe(ModelError("Groq is rate limiting requests.", try_next=True, retry_after=2))[1])
