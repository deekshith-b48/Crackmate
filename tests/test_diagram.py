import unittest

from pydantic import ValidationError

from core.export import diagram_markdown
from core.schemas import Diagram
from ui.diagram import diagram_html

GOOD = 'flowchart LR\n  A["Browser"] --> B["API"]\n  B --> C["DB (Assumption)"]:::assumed'


class DiagramTests(unittest.TestCase):
    def test_validation(self):
        Diagram(diagram=GOOD, assumptions="DB (Assumption)")
        for bad in ("sequenceDiagram\n  A->>B: hi hi hi hi", "```mermaid\nflowchart LR\nA-->B```",
                    '%%{init: {"securityLevel":"loose"}}%%\nflowchart LR\nA-->B'):
            with self.assertRaises(ValidationError):
                Diagram(diagram=bad, assumptions="x")

    def test_html_escapes_markup(self):
        out = diagram_html('flowchart LR\nA["<script>alert(1)</script>"] --> B')
        self.assertNotIn("<script>alert", out)
        self.assertIn("securityLevel", out)

    def test_markdown_has_fence(self):
        self.assertIn("```mermaid", diagram_markdown("API", Diagram(diagram=GOOD, assumptions="x")))
