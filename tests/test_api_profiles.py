from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import json
import unittest

from fastapi.testclient import TestClient

from api.deps import Core
from api.main import create_app
from core.config import Settings
from core.material import Material
from core.schemas import ProfileDraft
from core.storage import Storage


def make(directory):
    settings = Settings(api_key="synthetic", database=Path(directory) / "t.sqlite3")
    store = Storage(settings.database)
    service = Mock()
    return Core(settings, store, service, Material(store, service)), service


class ProfileApiTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.core, self.service = make(directory.name)
        self.client = TestClient(create_app(self.core, serve_web=False), base_url="http://127.0.0.1:8000",
                                 headers={"x-crackmate": "1"}, raise_server_exceptions=False)

    def events(self, response):
        return [json.loads(line) for line in response.text.splitlines() if line]

    def test_full_profile_lifecycle(self):
        record = self.client.post("/api/profiles").json()
        pid, rev = record["id"], record["revision"]
        details = {"revision": rev, "name": " Asha ", "role": "Backend", "skills": {"language": ["Python", "Python", " Go "]},
                   "work_experience": ["Intern\n", " "], "education": []}
        updated = self.client.put(f"/api/profiles/{pid}", json=details).json()
        self.assertEqual(updated["profile"]["name"], "Asha")
        self.assertEqual(updated["profile"]["skills"]["language"], ["Python", "Go"])
        self.assertEqual(updated["profile"]["work_experience"], ["Intern"])
        stale = self.client.put(f"/api/profiles/{pid}", json=details)  # old revision
        self.assertEqual(stale.status_code, 409)
        self.assertIn("another tab", stale.json()["message"])

        rev = updated["revision"]
        added = self.client.post(f"/api/profiles/{pid}/projects", json={"revision": rev, "title": "API", "technologies": ["FastAPI", "FastAPI"]}).json()
        project = added["profile"]["projects"][0]
        self.assertEqual(project["technologies"], ["FastAPI"])
        clar = self.client.put(f"/api/profiles/{pid}/projects/{project['id']}/clarification",
                               json={"revision": added["revision"], "answers": {"problem": " Slow ", "bogus": "x"}, "reference": "README"}).json()
        saved = clar["profile"]["projects"][0]
        self.assertEqual((saved["clarification"], saved["reference"]), ({"problem": "Slow"}, "README"))
        edited = self.client.put(f"/api/profiles/{pid}/projects/{project['id']}",
                                 json={"revision": clar["revision"], "title": "API v2", "contribution": "Caching"}).json()
        self.assertEqual(edited["profile"]["projects"][0]["title"], "API v2")
        self.assertEqual(edited["profile"]["projects"][0]["clarification"], {"problem": "Slow"})  # kept
        gone = self.client.delete(f"/api/profiles/{pid}/projects/{project['id']}", params={"revision": edited["revision"]}).json()
        self.assertEqual(gone["profile"]["projects"], [])

        self.assertEqual(self.client.delete(f"/api/profiles/{pid}").status_code, 400)  # needs confirm
        self.assertEqual(self.client.delete(f"/api/profiles/{pid}", params={"confirm": "true"}).status_code, 200)
        self.assertEqual(self.client.get(f"/api/profiles/{pid}").status_code, 404)

    def test_extract_needs_consent_and_saves_target(self):
        draft = ProfileDraft(name="Asha", projects=[{"title": "API"}])
        self.service.generate.return_value = (draft, "m")
        refused = self.events(self.client.post("/api/profile/extract", json={"text": "My resume", "consent": False}))
        self.assertEqual(refused[-1]["type"], "error")
        self.service.generate.assert_not_called()
        ok = self.events(self.client.post("/api/profile/extract", json={"text": "My resume", "consent": True, "role": " Backend ", "company": ""}))
        self.assertEqual(ok[-1]["type"], "result")
        profile = self.client.get(f"/api/profiles/{ok[-1]['data']['id']}").json()["profile"]
        self.assertEqual((profile["name"], profile["role"], profile["company"]), ("Asha", "Backend", None))
        self.assertEqual(self.service.generate.call_args.args[1], {"reviewed_resume": "My resume"})  # only the text is sent

    def test_resume_upload_and_friendly_errors(self):
        good = self.client.post("/api/resume/read", files={"file": ("cv.tex", b"\\section{Skills} Python", "text/plain")})
        self.assertIn("Python", good.json()["text"])
        bad = self.client.post("/api/resume/read", files={"file": ("cv.exe", b"MZ", "application/octet-stream")})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("PDF or LaTeX", bad.json()["message"])
        invalid = self.client.put("/api/profiles/x", json={"name": "no revision"})
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("missing or invalid", invalid.json()["message"])

    def test_form_labels(self):
        labels = self.client.get("/api/profile-form").json()
        self.assertIn("language", labels["skill_labels"])
        self.assertIn("problem", labels["clarifications"])
