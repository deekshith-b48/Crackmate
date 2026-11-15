from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from core.export import claims_markdown
from core.material import Material, claims_request
from core.schemas import ClaimReport, Profile, Project
from core.storage import Storage


def report():
    return ClaimReport(claims=[{
        "claim": "Improved performance by 40%", "source": "API", "kind": "metric", "risk": "high",
        "why": "No measurement method stated.", "probe": "How did you measure the 40%?",
        "defend": "Baseline, tool and load used.", "prepare": "Re-run a benchmark (Assumption)."}])


class ClaimTests(unittest.TestCase):
    def test_generate_reuse_and_export(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = Storage(Path(directory.name) / "t.sqlite3")
        record = store.create(Profile(projects=[Project(title="API", contribution="Caching")]))
        model = Mock()
        model.settings.model, model.settings.fallback_model, model.temperature = "m", "", 0.2
        model.generate.return_value = (report(), "m")
        material = Material(store, model)
        request = claims_request(record.profile)
        item, fresh = material.generate(record, request)
        self.assertTrue(fresh)
        self.assertEqual(material.generate(record, request), (item, False))
        model.generate.assert_called_once()
        self.assertNotIn("reference", request.context["projects"][0])
        text = claims_markdown(ClaimReport.model_validate_json(item.body), {0})
        self.assertIn("40%", text)
        self.assertIn("defended", text)


class OpenClaimsTests(unittest.TestCase):
    def test_only_unticked_medium_and_high_claims(self):
        from types import SimpleNamespace
        from core.review import ClaimTicks
        from ui.claims import open_claims
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = Storage(Path(directory.name) / "t.sqlite3")
        record = store.create(Profile(projects=[Project(title="API", contribution="Caching")]))
        claim = lambda text, risk: {"claim": text, "source": "API", "kind": "metric", "risk": risk, "why": "w",
                                    "probe": f"{text}?", "defend": "d", "prepare": "p"}
        model = Mock()
        model.settings.model, model.settings.fallback_model, model.temperature = "m", "", 0.2
        model.generate.return_value = (ClaimReport(claims=[claim("A", "high"), claim("B", "low"),
                                                           claim("C", "medium"), claim("D", "high")]), "m")
        material = Material(store, model)
        app = SimpleNamespace(profile=record.profile, record=record, store=store, material=material)
        self.assertEqual(open_claims(app), [])  # nothing saved yet
        item, _ = material.generate(record, claims_request(record.profile))
        ClaimTicks(store).set(record.id, item.digest, 3, True)  # D is defended
        self.assertEqual([c["claim"] for c in open_claims(app)], ["A", "C"])
