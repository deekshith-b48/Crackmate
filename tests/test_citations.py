from types import SimpleNamespace
import unittest

from core.material import validate_citations

EVIDENCE = [{"id": "p1", "text": "A cache stores recent results."}]
cite = lambda pid, quote="": SimpleNamespace(passage_id=pid, quote=quote)


class CitationRuleTests(unittest.TestCase):
    def test_citing_is_optional_by_default_so_good_answers_are_not_thrown_away(self):
        none = SimpleNamespace(citations=[])
        validate_citations(none, EVIDENCE)  # a lesson or feedback that cites nothing is accepted
        with self.assertRaises(ValueError):
            validate_citations(none, EVIDENCE, required=True)  # still available when a caller insists
        validate_citations(none, [], required=True)  # nothing to cite
        validate_citations(SimpleNamespace(citations=[cite("p1", "stores recent")]), EVIDENCE)

    def test_citations_that_point_nowhere_are_always_rejected(self):
        for required in (True, False):
            with self.assertRaisesRegex(ValueError, "unavailable passage"):
                validate_citations(SimpleNamespace(citations=[cite("nope")]), EVIDENCE, required=required)
            with self.assertRaisesRegex(ValueError, "Quotation"):
                validate_citations(SimpleNamespace(citations=[cite("p1", "an invented quote")]), EVIDENCE, required=required)


class EvidenceNoteTests(unittest.TestCase):
    def test_a_lesson_that_cites_nothing_says_so(self):
        from core.export import evidence_markdown
        uncited = SimpleNamespace(evidence=[{"id": "p1", "title": "T", "location": "L", "retrieved": "d", "license": "MIT"}], citations=[])
        self.assertIn("general model knowledge", evidence_markdown(uncited))
        self.assertNotIn("Reuse terms", evidence_markdown(uncited))
