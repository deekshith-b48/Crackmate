from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from core.learning import Learning, RUBRIC, topic_id, validate_catalogue, export_progress
from core.storage import Storage
from core.schemas import Profile
from test_interview import feedback


class LearningTests(unittest.TestCase):
    def setUp(self):
        directory=TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store=Storage(Path(directory.name)/"db")
        self.record=self.store.create(Profile())
        self.learning=Learning(self.store,self.record.id)
        self.now=datetime(2026,11,14,20,tzinfo=timezone.utc)
        self.topic=topic_id("Networking")

    def add(self, ident, at, **changes):
        metadata=dict(rubric=RUBRIC,difficulty="Basics",hint=False,revealed=False,retry=False,independent=True)
        metadata.update(changes)
        self.learning.ingest("diagnostic:"+ident,"Networking",ident,feedback(),at=at.isoformat(),metadata=metadata)

    def state(self):
        return next(t for t in self.learning.progress(self.now) if t["id"]==self.topic)

    def test_sparse_assisted_and_timezone_scheduling(self):
        self.add("first",self.now)
        self.assertEqual(self.state()["state"],"Learning")
        self.assertEqual(self.state()["due"],"2026-11-16")
        self.add("second",self.now+timedelta(seconds=1))
        self.assertEqual(self.state()["state"],"Demonstrated recently")
        self.add("assisted",self.now+timedelta(seconds=2),hint=True,independent=False)
        self.assertEqual(self.state()["state"],"Learning")
        self.assertEqual(self.state()["due"],"2026-11-16")

    def test_cycle_and_missing_reference(self):
        with self.assertRaises(ValueError):
            validate_catalogue([dict(id="a",prerequisites=["b"]),dict(id="b",prerequisites=["a"])])
        with self.assertRaises(ValueError):
            validate_catalogue([dict(id="a",prerequisites=["unknown"])])

    def test_idempotent_history_and_rubric_unknown(self):
        self.store.save_attempt(self.record,"one","Networking","What is TCP?","Answer",feedback())
        self.learning.sync()
        self.learning.sync()
        self.assertEqual(len(self.learning.evidence()),1)
        self.assertEqual(self.state()["count"],0)
        self.assertEqual(self.state()["state"],"Learning")
        Learning(self.store,self.record.id)
        self.assertEqual(len(self.learning.evidence()),1)

    def test_preferences_and_budget_preserve_completed(self):
        self.learning.preference("queue:"+self.topic,{"pinned":True})
        self.assertEqual(self.learning.queue(self.now,30)[0]["topic"],self.topic)
        self.learning.preference("queue:"+self.topic,{"dismissed":True})
        self.assertNotIn(self.topic,[r["topic"] for r in self.learning.queue(self.now,240)])
        proposal=self.learning.propose(self.now)
        self.learning.apply_plan(proposal)
        first=proposal["blocks"][0]
        self.learning.update_block(first["id"],"completed",True)
        revised=self.learning.propose(self.now)
        self.assertTrue(next(b for b in revised["blocks"] if b["id"]==first["id"])["completed"])
        for date in {b["date"] for b in revised["blocks"]}:
            self.assertLessEqual(sum(b["duration"] for b in revised["blocks"] if b["date"]==date),60)
        settings=self.learning.settings() | {"interview":"2026-11-01"}
        self.learning.preference("settings",settings)
        with self.assertRaises(ValueError):
            self.learning.propose(self.now)

    def test_deletion_recomputes_and_profile_cascade(self):
        self.store.save_attempt(self.record,"one","Networking","What is TCP?","Answer",feedback())
        self.learning.sync()
        with self.store.connect() as db:
            db.execute("DELETE FROM attempts WHERE profile_id=?",(self.record.id,))
        self.learning.sync()
        self.assertEqual(self.learning.evidence(),[])
        self.assertIn("0 compatible scored attempts",export_progress(self.learning,self.now))
        self.store.delete(self.record.id)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM learning_topics").fetchone()[0],0)
