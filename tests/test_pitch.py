from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from core.export import pitch_markdown
from core.material import Material, pitch_request
from core.schemas import Pitch, Profile, Project
from core.storage import Storage


def pitch(words=280):
    return Pitch(opening="I built an API.", pitch=" ".join(["word"] * words),
                 key_points=["a", "b", "c"], assumptions="None.")


class PitchTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Storage(Path(directory.name) / "t.sqlite3")
        self.record = self.store.create(Profile(projects=[Project(title="API")]))
        self.request = pitch_request(self.record.profile, self.record.profile.projects[0])

    def test_length_validator_and_export(self):
        self.request.validate(pitch(280))
        for bad in (50, 600):
            with self.assertRaises(ValueError):
                self.request.validate(pitch(bad))
        self.assertIn("2 minutes", pitch_markdown("API", pitch()))

    def test_saved_and_reused(self):
        model = Mock()
        model.settings.model, model.settings.fallback_model, model.temperature = "m", "", 0.2
        model.generate.return_value = (pitch(), "m")
        material = Material(self.store, model)
        item, fresh = material.generate(self.record, self.request)
        self.assertEqual(material.generate(self.record, self.request), (item, False))
        model.generate.assert_called_once()
