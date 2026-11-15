from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from core.material import Material, ladder_request
from core.schemas import LADDER, Ladder, Profile
from core.storage import Storage


def steps(order=LADDER):
    return [{"level": level, "question": f"{level}?", "answer": "An answer."} for level in order]


class LadderTests(unittest.TestCase):
    def test_order_enforced(self):
        Ladder(steps=steps())
        with self.assertRaises(ValidationError):
            Ladder(steps=steps(reversed(LADDER)))

    def test_saved_and_reused(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = Storage(Path(directory.name) / "t.sqlite3")
        record = store.create(Profile())
        model = Mock()
        model.settings.model, model.settings.fallback_model, model.temperature = "m", "", 0.2
        model.generate.return_value = (Ladder(steps=steps()), "m")
        material = Material(store, model)
        request = ladder_request(record.profile, "skill:Basics:REST", "abc", "What is REST?", "A style.")
        item, fresh = material.generate(record, request)
        self.assertEqual(material.generate(record, request), (item, False))
        model.generate.assert_called_once()
