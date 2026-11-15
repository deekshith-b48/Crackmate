from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from core import company
from core.ingest import ingest, sections
from core.knowledge import Library
from core.storage import Storage

BODY = "# Cache\n\n" + "A cache stores recent results so repeated reads skip the slow database. " * 6


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.library = Library(Storage(self.root / "db.sqlite3"))

    def tree(self):
        repo = self.root / "clones" / "demo"
        for name, text in {"README.md": BODY, "notes/lb.md": "# Load balancer\n\n" + "A load balancer spreads requests. " * 12,
                           "translations/README.md": BODY, "README-ja.md": BODY, "tiny.md": "# Tiny\n\nshort"}.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        (repo / "link.md").symlink_to(self.root / "db.sqlite3")
        return self.root / "clones", (("demo", "https://github.com/x/demo", "CC BY 4.0 · Someone", ""),)

    def test_skips_translations_links_and_tiny_files_and_is_repeatable(self):
        clones, repos = self.tree()
        first = ingest(self.library, clones, repos, log=lambda _: None)
        self.assertEqual(first["Imported"], 2)
        self.assertEqual(ingest(self.library, clones, repos, log=lambda _: None)["Unchanged"], 2)
        found = self.library.search("cache database")[0]
        self.assertEqual((found["license"], found["location"]),
                         ("CC BY 4.0 · Someone", "https://github.com/x/demo/blob/HEAD/README.md"))

    def test_large_files_split_by_section_and_caps_are_separate(self):
        big = "# Guide\n\nintro\n\n" + "".join(f"## Part {n}\n\n" + "text " * 100 + "\n\n" for n in range(300))
        self.assertGreater(len(big), 90_000)
        parts = sections(big)
        self.assertGreater(len(parts), 100)
        self.assertTrue(all(len(body) <= 90_000 for _, body in parts))
        for n in range(100):
            self.library.import_text(f"t{n}", f"repo:{n}", f"text {n} " * 40, "repo", bulk=True)
        self.library.import_text("mine", "own:1", "My own notes about caching.")  # unaffected by repo count
        self.assertEqual(len(self.library.sources()), 101)


class CompanyTests(unittest.TestCase):
    CSV = ("Difficulty,Title,Frequency,Acceptance Rate,Link,Topics\n"
           'EASY,Two Sum,100.0,0.5,https://leetcode.com/problems/two-sum,"Array, Hash Table"\n'
           'HARD,Evil,99.0,0.1,javascript:alert(1),"Array"\n'
           'MEDIUM,LRU Cache,80.5,0.4,https://leetcode.com/problems/lru-cache,"Hash Table, Design"\n')

    def test_parse_drops_foreign_links_sorts_and_tallies(self):
        rows = company.parse_problems(self.CSV)
        self.assertEqual([r["Title"] for r in rows], ["Two Sum", "LRU Cache"])
        self.assertEqual(rows[0]["Difficulty"], "Easy")
        self.assertEqual(company.focus_topics(rows)[0], ("Hash Table", 2))

    def test_stale_cache_used_when_offline_and_friendly_error_without(self):
        with TemporaryDirectory() as d, patch.object(company, "CACHE", Path(d)), \
                patch.object(company, "fetch", side_effect=ValueError("down")):
            with self.assertRaisesRegex(ValueError, "could not be loaded"):
                company.cached("https://example.com/a")
            (Path(d) / (company.hashlib.sha256(b"https://example.com/a").hexdigest()[:16] + ".txt")).write_text("old")
            self.assertEqual(company.cached("https://example.com/a", hours=0), "old")


class TitleTests(unittest.TestCase):
    def test_titles_ignore_code_comments_and_use_frontmatter(self):
        from core.ingest import page_title
        self.assertEqual(page_title("```py\n# comment\n```\n# Real Title\n", "x"), "Real Title")
        self.assertEqual(page_title('---\ntitle: "Hash Table"\n---\n# Other', "x"), "Hash Table")
        self.assertEqual(page_title("no headings", "stem"), "stem")
