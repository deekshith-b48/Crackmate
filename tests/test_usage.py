from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys
import unittest

from core.config import Settings
from core.llm import ModelService
from core.material import Material, skill_request
from core.schemas import Profile, ProfileDraft
from core.storage import Storage
from core.usage import Usage

sys.path.insert(0, str(Path(__file__).parent))
from test_material import skill_lesson  # noqa: E402


def completion(body, tokens=(120, 80)):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=body))],
                           usage=SimpleNamespace(prompt_tokens=tokens[0], completion_tokens=tokens[1]))


class UsageTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Storage(Path(directory.name) / "t.sqlite3")
        self.usage = Usage(self.store)

    def test_live_calls_are_logged_with_feature_model_and_tokens(self):
        service = ModelService(Settings(api_key="synthetic", fast_model=""))
        service.usage_sink = self.usage.add
        with patch("core.llm.Groq") as client:
            client.return_value.__enter__.return_value.chat.completions.create = Mock(return_value=completion("{}"))
            service.generate("profile", {"reviewed_resume": "x"}, ProfileDraft)
        s = self.usage.summary()
        self.assertEqual((s["calls"], s["cached"], s["tokens_in"], s["tokens_out"]), (1, 0, 120, 80))
        self.assertEqual(s["by_feature"][0]["feature"], "profile")
        self.assertEqual(s["by_model"][0]["remaining"], s["by_model"][0]["limit"] - 200)

    def test_cache_hits_count_as_saved_calls(self):
        model = Mock()
        model.settings.model, model.settings.fallback_model, model.temperature = "m", "", 0.2
        model.generate.return_value = (skill_lesson(), "m")
        model.usage_sink = self.usage.add
        material = Material(self.store, model)
        record = self.store.create(Profile())
        request = skill_request(record.profile, "Caching", "Basics")
        material.generate(record, request)                 # generated: no cache hit
        material.generate(record, request)                 # saved lesson
        other = self.store.create(Profile(role="Other"))
        material.generate(other, skill_request(other.profile, "Caching", "Basics"))  # shared lesson
        s = self.usage.summary()
        self.assertEqual(s["cached"], 2)
        self.assertGreater(s["saved_tokens"], 0)

    def test_logging_failures_never_break_a_request(self):
        service = ModelService(Settings(api_key="synthetic", fast_model=""))
        service.usage_sink = Mock(side_effect=RuntimeError("disk full"))
        with patch("core.llm.Groq") as client:
            client.return_value.__enter__.return_value.chat.completions.create = Mock(return_value=completion("{}"))
            result, _ = service.generate("profile", {"reviewed_resume": "x"}, ProfileDraft)
        self.assertIsNotNone(result)
        broken = Usage(self.store)
        broken.store = Mock(connect=Mock(side_effect=__import__("sqlite3").OperationalError("locked")))
        broken.add("x", "m", 1, 1)  # must not raise

    def test_empty_summary_and_endpoint(self):
        s = self.usage.summary()
        self.assertEqual((s["calls"], s["cached"], s["saved_tokens"], s["by_model"]), (0, 0, 0, []))
        from fastapi.testclient import TestClient
        from api.deps import Core
        from api.main import create_app
        settings = Settings(api_key="k", database=self.store.path)
        service = ModelService(settings)
        client = TestClient(create_app(Core(settings, self.store, service, Material(self.store, service)), serve_web=False), base_url="http://127.0.0.1:8000")
        self.usage.add("claims", "m", 10, 5)
        body = client.get("/api/usage").json()
        self.assertEqual((body["calls"], body["by_feature"][0]["feature"]), (1, "claims"))
        self.assertIn("shared by your whole organisation", body["note"])
