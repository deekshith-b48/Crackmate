import threading
import time
import unittest
from unittest.mock import Mock

from core.llm import ModelError
from core.material import generate_many


class Req:
    def __init__(self, slot):
        self.slot = self.title = slot


class ParallelTests(unittest.TestCase):
    def test_parallel_skips_current_and_reports_failures(self):
        material = Mock()
        material.store.item.return_value = None
        material.current.side_effect = lambda record, request, item: request.slot == "have"
        running, peak, lock = 0, 0, threading.Lock()

        def generate(record, request):
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.05)
            with lock:
                running -= 1
            if request.slot == "bad":
                raise ModelError("nope")

        material.generate.side_effect = generate
        steps = []
        done, failed = generate_many(material, Mock(id="p"), [Req(s) for s in ("a", "b", "c", "have", "bad")],
                                     progress=steps.append)
        self.assertEqual((done, failed), (3, ["bad"]))
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 3)
        self.assertEqual(len(steps), 4)
