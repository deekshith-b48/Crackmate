import unittest

from core.learning import RUBRIC, readiness


def evidence(scores, independent=True, rubric=RUBRIC, time="2026-11-14T10:00:00+00:00"):
    return {"rubric": rubric, "time": time, "independent": independent,
            "scores": dict(zip(("accuracy", "coverage", "reasoning", "clarity"), scores))}


class ReadinessTests(unittest.TestCase):
    def test_scores_caps_and_coverage(self):
        progress = [
            {"id": "a", "evidence": [evidence((4, 4, 4, 4))]},
            {"id": "b", "evidence": [evidence((4, 4, 4, 4), independent=False)]},  # assisted: capped at 70
            {"id": "c", "evidence": [evidence((2, 2, 2, 2), rubric="other")]},  # incompatible rubric
            {"id": "d", "evidence": []},
            {"id": "e", "evidence": [evidence((0, 0, 0, 0)), evidence((4, 4, 4, 4)), evidence((4, 4, 4, 4))]},
        ]
        overall, assessed, total, scores = readiness(progress)
        self.assertEqual(scores, {"a": 100, "b": 70, "c": None, "d": None, "e": 67})
        self.assertEqual((assessed, total, overall), (3, 5, 79))

    def test_nothing_assessed(self):
        self.assertEqual(readiness([{"id": "a", "evidence": []}])[:3], (None, 0, 1))
