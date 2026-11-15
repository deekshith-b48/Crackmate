from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.review import Reviews, sm2
from core.schemas import Profile
from core.storage import Storage


class ReviewTests(unittest.TestCase):
    def test_sm2_progression_and_lapse(self):
        ease, interval, reps = sm2(2.5, 0, 0, 4)
        self.assertEqual((interval, reps), (1, 1))
        ease, interval, reps = sm2(ease, interval, reps, 4)
        self.assertEqual(interval, 6)
        self.assertEqual(sm2(ease, interval, reps, 5)[1], round(6 * ease))
        self.assertEqual(sm2(ease, interval, reps, 1)[1:], (0, 0))
        self.assertGreaterEqual(sm2(1.3, 6, 2, 3)[0], 1.3)

    def test_queue_and_cascade_delete(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = Storage(Path(directory.name) / "t.sqlite3")
        record = store.create(Profile())
        reviews, today = Reviews(store), date(2026, 11, 14)
        self.assertEqual(reviews.rate(record.id, "s", "Q1?", "A", "h", "Again", today), 0)
        self.assertEqual(reviews.rate(record.id, "s", "Q2?", "A", "h", "Good", today), 1)
        self.assertEqual([r["question"] for r in reviews.due(record.id, today)], ["Q1?"])
        self.assertEqual(len(reviews.due(record.id, date(2026, 11, 15))), 2)
        store.delete(record.id)
        self.assertEqual(reviews.due(record.id, date(2030, 1, 1)), [])


class TickTests(unittest.TestCase):
    def test_ticks_persist_and_cascade(self):
        from core.review import ClaimTicks
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = Storage(Path(directory.name) / "t.sqlite3")
        record = store.create(Profile())
        ticks = ClaimTicks(store)
        ticks.set(record.id, "d1", 2, True)
        ticks.set(record.id, "d1", 0, True)
        ticks.set(record.id, "d1", 0, False)
        self.assertEqual(ticks.get(record.id, "d1"), {2})
        self.assertEqual(ticks.get(record.id, "d2"), set())
        store.delete(record.id)
        self.assertEqual(ticks.get(record.id, "d1"), set())
