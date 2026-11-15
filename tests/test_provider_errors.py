import unittest
from unittest.mock import patch

from groq import APIStatusError
from httpx import Request, Response

from core.config import Settings
from core.llm import ModelError, ModelService
from core.schemas import ProfileDraft
from test_profiles import completion


def status(code, *, headers=None, error_code=""):
    response = Response(code, headers=headers, request=Request("POST", "https://api.groq.com"))
    return APIStatusError("provider-private-data", response=response, body={"error": {"code": error_code}})


class ProviderErrorTests(unittest.TestCase):
    def setUp(self):
        self.service = ModelService(Settings(api_key="synthetic", fallback_model="test-fallback", fast_model=""))
        client = patch("core.llm.Groq")
        self.addCleanup(client.stop)
        self.call = client.start().return_value.__enter__.return_value.chat.completions.create

    def generate(self):
        return self.service.generate("profile", {"reviewed_resume": "synthetic"}, ProfileDraft)

    def test_invalid_key_does_not_retry_or_expose_provider_payload(self):
        self.call.side_effect = status(401)
        with self.assertRaisesRegex(ModelError, "rejected access") as result:
            self.generate()
        self.assertNotIn("provider-private-data", str(result.exception))
        self.call.assert_called_once()

    def test_rate_limit_honors_retry_after(self):
        self.call.side_effect = [status(429, headers={"retry-after": "2"}), completion("{}")]
        with patch("core.llm.time.sleep") as sleep:
            self.generate()
        sleep.assert_called_once_with(2)
        self.assertEqual(self.call.call_count, 2)

    def test_exhausted_quota_never_uses_fallback(self):
        self.call.side_effect = status(429, headers={"x-ratelimit-remaining-requests": "0"})
        with self.assertRaisesRegex(ModelError, "quota is exhausted"):
            self.generate()
        self.call.assert_called_once()

    def test_missing_model_uses_configured_fallback(self):
        self.call.side_effect = [status(404), completion("{}")]
        _, model = self.generate()
        self.assertEqual(model, "test-fallback")
        self.assertEqual(self.call.call_args.kwargs["model"], model)

    def test_small_tasks_use_fast_model_and_teaching_uses_large(self):
        self.service.settings = Settings(api_key="synthetic", model="big", fast_model="small")
        self.call.side_effect = [completion("{}")]
        self.assertEqual(self.generate()[1], "small")
        self.assertEqual(self.service.chain("skill"), ["big"])

    def test_persistent_rate_limit_falls_back_after_backoff(self):
        self.call.side_effect = [status(429)] * 3 + [completion("{}")]
        with patch("core.llm.time.sleep") as sleep:
            _, model = self.generate()
        self.assertEqual(model, "test-fallback")
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1.0, 2.0])

    def test_rate_limited_groq_falls_back_to_second_provider(self):
        self.service.settings = Settings(api_key="g", fast_model="", alt_api_key="a", alt_base_url="https://alt.example/v1", alt_model="alt-m")
        self.call.side_effect = [status(429)] * 3 + [completion("{}")]
        with patch("core.llm.time.sleep"):
            _, model = self.generate()
        self.assertEqual(model, "alt-m")
        with patch("core.llm.Groq") as groq:  # not configured: Groq alone, no second client
            self.service.settings = Settings(api_key="g", fast_model="")
            self.assertEqual(len(self.service._routes(object(), ["m"])), 1)

    def test_stream_yields_chunks_and_never_raises(self):
        chunk = lambda t: type("E", (), {"choices": [type("C", (), {"delta": type("D", (), {"content": t})()})()]})()
        self.call.return_value = iter([chunk("Hel"), chunk("lo")])
        self.assertEqual("".join(self.service.stream("s", "u")), "Hello")
        self.call.side_effect = status(500)
        self.assertIn("try again", "".join(self.service.stream("s", "u")))
