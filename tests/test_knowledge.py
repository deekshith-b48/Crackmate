from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from core.knowledge import Library, chunks
from core.storage import Storage
from core.schemas import Profile
from core.fetch import destination


class KnowledgeTests(unittest.TestCase):
    def test_repeatable_migration_refresh_search_delete(self):
        with TemporaryDirectory() as directory:
            store=Storage(Path(directory)/"db")
            profile=store.create(Profile())
            library=Library(store)
            library.import_text("TCP","local:tcp","TCP uses sequence numbers.\n\nTCP retransmits lost packets.")
            self.assertEqual(library.import_text("TCP","local:tcp","TCP uses sequence numbers.\n\nTCP retransmits lost packets."),"Unchanged")
            source=library.sources()[0]
            library.failed(source["id"],"Offline")
            self.assertTrue(library.search("TCP"))
            Library(store)
            self.assertIsNotNone(store.get(profile.id))
            library.import_text("TCP","local:tcp","TCP provides reliable byte streams.")
            self.assertIn("reliable",library.search("TCP")[0]["text"])
            library.delete(source["id"])
            self.assertEqual(library.search("TCP"),[])

    def test_blocks_private_and_credentials(self):
        with patch("core.fetch.socket.getaddrinfo", return_value=[(2,1,6,"",("127.0.0.1",80))]):
            with self.assertRaises(ValueError):
                destination("http://example.com")
        with self.assertRaises(ValueError):
            destination("https://user:pass@example.com")

    def test_chunk_bounds(self):
        self.assertTrue(all(len(body)<=1600 for _,body in chunks("# Heading\n\n"+"a"*5000)))
