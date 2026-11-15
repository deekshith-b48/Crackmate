from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import shutil
import subprocess
import unittest

from fastapi.testclient import TestClient

from api.deps import Core
from api.main import create_app
from core.career import facts, gitlog, graph, secrets
from core.career import repo as repo_mod
from core.career.ontology import REQUIRES, TECH_CONCEPTS, canon
from core.config import Settings
from core.llm import ModelService
from core.material import COMMON_TOPICS, CORE_TOPICS, Material
from core.schemas import Profile, Project
from core.storage import Storage

FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"  # built at runtime so this file is not itself a finding
APP_JS = "import React from 'react';\nimport express from 'express';\nimport Redis from 'ioredis';\nconst x = 1;\n" * 3


def make_repo(path):
    """A tiny real git repository with two authors, so ownership and hotspots are real git output."""
    def git(*args, who=("Asha", "asha@example.com")):
        env = {**os.environ, "GIT_AUTHOR_NAME": who[0], "GIT_AUTHOR_EMAIL": who[1], "GIT_COMMITTER_NAME": who[0], "GIT_COMMITTER_EMAIL": who[1]}
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, env=env)
    path.mkdir(parents=True)
    git("init", "-q")
    (path / "src").mkdir()
    (path / "package.json").write_text(json.dumps({"dependencies": {"react": "18", "express": "4", "pg": "8"}, "devDependencies": {"jest": "29"}}))
    (path / "Dockerfile").write_text("FROM node:20\n")
    (path / ".github" / "workflows").mkdir(parents=True)
    (path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (path / "src" / "app.js").write_text(APP_JS)
    (path / "src" / "app.test.js").write_text("test('x', () => {});\n")
    (path / "config.js").write_text(f'const key = "{FAKE_AWS}";\n')
    git("add", "-A"); git("commit", "-qm", "initial app")
    for n in range(3):  # asha keeps changing app.js: a hotspot
        (path / "src" / "app.js").write_text(APP_JS + f"// change {n}\n" * 10)
        git("commit", "-qam", f"tweak {n}")
    (path / "src" / "team.js").write_text("export const team = 1;\n" * 40)
    git("add", "-A"); git("commit", "-qm", "teammate adds a module", who=("Ben", "ben@example.com"))
    return path


class PureLayerTests(unittest.TestCase):
    def test_ontology_names_are_real_lesson_topics_and_acyclic(self):
        topics = set(CORE_TOPICS) | set(COMMON_TOPICS)
        names = {c for v in TECH_CONCEPTS.values() for c in v} | set(REQUIRES) | {c for v in REQUIRES.values() for c in v}
        self.assertEqual(names - topics, set())
        state = {}
        def visit(n):
            if state.get(n) == 1:
                self.fail(f"prerequisite cycle at {n}")
            if state.get(n) == 2:
                return
            state[n] = 1
            for m in REQUIRES.get(n, []):
                visit(m)
            state[n] = 2
        for n in REQUIRES:
            visit(n)
        self.assertEqual((canon("React.js"), canon("Node.js"), canon("SQLite (FTS5)"), canon("Postgres")), ("react", "node.js", "sqlite", "postgresql"))

    def test_dependency_parsers_and_malformed_input(self):
        self.assertEqual(facts.parse_dependencies("requirements.txt", "fastapi==0.1\n# c\nuvicorn[standard]>=1\n-r other.txt\n"), ["fastapi", "uvicorn"])
        self.assertEqual(facts.parse_dependencies("pyproject.toml", '[project]\ndependencies=["redis>=5","pydantic"]\n'), ["redis", "pydantic"])
        self.assertEqual(facts.parse_dependencies("pom.xml", "<artifactId>spring-boot-starter-web</artifactId>"), ["spring-boot-starter-web"])
        self.assertEqual(facts.parse_dependencies("docker-compose.yml", "services:\n  db:\n    image: postgres:16\n  c:\n    image: redis:7\n"), ["docker", "postgres", "redis"])
        for bad in ("{not json", "", "\x00\x01"):
            self.assertEqual(facts.parse_dependencies("package.json", bad), [])
        self.assertEqual(facts.parse_dependencies("pyproject.toml", "= broken ="), [])

    def test_detect_confidence_levels(self):
        found = {t["name"]: t for t in facts.detect({"package.json": '{"dependencies":{"react":"1","pg":"1"}}', "src/a.js": "import React from 'react'\nimport redisClient from 'ioredis'",
                                                    "Dockerfile": "FROM x", ".github/workflows/ci.yml": "n", "tests/a.test.js": ""})["technologies"]}
        self.assertEqual(found["react"]["confidence"], 0.9)  # seen in code beats a manifest
        self.assertEqual(found["redis"]["confidence"], 0.9)
        self.assertEqual(found["postgresql"]["confidence"], 0.8)
        self.assertTrue({"docker", "github actions", "testing"} <= set(found))

    def test_languages_and_manifests_count_as_evidence(self):
        found = {t["name"]: t for t in facts.detect({"package.json": "{}", "a.ts": "const x = 1", "b.py": "x = 1"})["technologies"]}
        self.assertTrue({"node.js", "typescript", "python"} <= set(found))
        self.assertEqual(found["node.js"]["evidence"][0]["file"], "package.json")

    def test_secret_scan_masks_values_and_skips_placeholders(self):
        files = {"a.js": f'k = "{FAKE_AWS}"\napi_key = "your-api-key-here-123"\npassword = "hunter2hunter2hunter2"\n', ".env": "X=1", ".env.example": "X=1", "process.js": 'const t = process.env.TOKEN_VALUE_LONG_ENOUGH'}
        found = secrets.scan(files)
        kinds = sorted((f["file"], f["kind"]) for f in found)
        self.assertIn(("a.js", "AWS access key"), kinds)
        self.assertIn(("a.js", "Hard-coded credential"), kinds)
        self.assertIn((".env", "A .env file is committed"), kinds)
        self.assertEqual(len([f for f in found if f["file"] == "a.js"]), 2)  # the placeholder was ignored
        self.assertNotIn(FAKE_AWS, json.dumps(found))

    def test_symlinks_and_vendored_dirs_are_skipped(self):
        with TemporaryDirectory() as d:
            root = Path(d); (root / "node_modules").mkdir(); (root / "node_modules" / "x.js").write_text("import a from 'react'")
            (root / "real.py").write_text("import redis\n"); (root / "link.py").symlink_to("/etc/hosts")
            self.assertEqual(sorted(facts.read_repo(root)), ["real.py"])


class GraphTests(unittest.TestCase):
    def build(self, **kw):
        profile = Profile(name="Asha", projects=[Project(title="API", technologies=["React.js", "Node.js", "MongoDB", "Redis"])], **kw)
        found = {profile.projects[0].id: facts.detect({"package.json": '{"dependencies":{"react":"1","pg":"1"}}', "a.js": "import React from 'react'"})}
        return profile, graph.build(profile, found), found

    def test_edges_carry_confidence_and_claims_are_judged_against_code(self):
        profile, built, _ = self.build()
        edge = next(e for e in built["edges"] if e["target"] == "tech:react" and e["kind"] == "uses")
        self.assertEqual(edge["confidence"], 1.0)  # stated in the resume
        self.assertEqual(sorted(u["technology"] for u in built["unsupported"]), ["mongodb", "redis"])  # node.js is backed by package.json
        self.assertEqual(sorted(u["technology"] for u in built["undeclared"]), ["javascript", "postgresql"])
        self.assertIn("concept:Indexing", {n["id"] for n in built["nodes"]})  # from MongoDB and PostgreSQL
        self.assertIn("concept:SQL queries and joins", {n["id"] for n in built["nodes"]})  # pulled in as a prerequisite

    def test_no_repo_means_no_judgement(self):
        profile = Profile(projects=[Project(title="API", technologies=["Redis"])])
        built = graph.build(profile, {})
        self.assertEqual((built["unsupported"], built["undeclared"]), ([], []))

    def test_blast_radius_follows_prerequisites_to_projects(self):
        _, built, _ = self.build()
        out = graph.blast_radius(built, "Database fundamentals")
        self.assertIn("Indexing", out["concepts"])
        self.assertIn("mongodb", out["technologies"])
        self.assertEqual(out["projects"], ["API"])


class GitTests(unittest.TestCase):
    def test_ownership_and_hotspots_from_real_git(self):
        with TemporaryDirectory() as d:
            root = make_repo(Path(d) / "r")
            commits = gitlog.parse_log(gitlog.read_log(root))
            self.assertEqual(len(commits), 5)
            names = {a["name"] for a in gitlog.authors(commits)}
            self.assertEqual(names, {"Asha", "Ben"})
            own = gitlog.ownership(commits, ["asha@example.com"])
            self.assertTrue(0.3 < own["share"] < 0.95)
            self.assertEqual([f["path"] for f in own["files_not_yours"]], ["src/team.js"])
            self.assertEqual(gitlog.ownership(commits, [])["files_not_yours"], [])  # unknown identity: no claims about "not yours"
            self.assertEqual(gitlog.hotspots(commits, ["asha@example.com"])[0]["path"], "src/app.js")
            noisy = gitlog.parse_log("@@a\x1fx@y\x1fX\x1f1\x1fm\n5\t5\tpackage.json\n9\t1\tlib/core.py\n@@b\x1fx@y\x1fX\x1f2\x1fm\n5\t5\tpackage.json\n9\t1\tlib/core.py\n")
            self.assertEqual([h["path"] for h in gitlog.hotspots(noisy, [])], ["lib/core.py"])  # config files are not talking points
            self.assertEqual(gitlog.parse_log("garbage\n\t\t\n"), [])


class ApiTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.fixture = make_repo(root / "fixture")
        settings = Settings(api_key="synthetic", database=root / "t.sqlite3")
        store = Storage(settings.database)
        service = ModelService(settings)
        self.core = Core(settings, store, service, Material(store, service))
        self.client = TestClient(create_app(self.core, serve_web=False), base_url="http://127.0.0.1:8000", headers={"x-crackmate": "1"}, raise_server_exceptions=False)
        for target, value in (("core.career.repo.REPOS", root / "repos"),):
            p = patch(target, value); p.start(); self.addCleanup(p.stop)
        self.clones = []
        def fake_clone(url, dest):
            self.clones.append(url)
            shutil.copytree(self.fixture, dest)
        p = patch("core.career.repo.clone", fake_clone); p.start(); self.addCleanup(p.stop)
        self.head = repo_mod.head_commit(self.fixture)  # the real remote HEAD for the fixture repository
        p = patch("core.career.repo.remote_head", lambda url: self.head); p.start(); self.addCleanup(p.stop)
        self.pid = self.client.post("/api/profiles").json()["id"]
        rev = self.client.get(f"/api/profiles/{self.pid}").json()["revision"]
        added = self.client.post(f"/api/profiles/{self.pid}/projects", json={"revision": rev, "title": "Shop", "technologies": ["React.js", "Express.js", "MongoDB"]}).json()
        self.project = added["profile"]["projects"][0]["id"]
        self.base = f"/api/profiles/{self.pid}/career"

    def run_stream(self, path, body):
        events = [json.loads(l) for l in self.client.post(self.base + path, json=body).text.splitlines() if l]
        return events[-1]

    def test_repo_lifecycle_is_incremental_and_never_leaks_secrets(self):
        url = "https://github.com/asha/shop"
        first = self.run_stream("/repos", {"project_id": self.project, "url": url})
        self.assertEqual(first["type"], "result", first)
        repo = first["data"]["repo"]
        self.assertTrue(first["data"]["changed"])
        self.assertEqual(first["data"]["repo"]["facts"]["loc"] > 0, True)
        self.assertNotIn(FAKE_AWS, json.dumps(first))
        self.assertEqual([s["kind"] for s in repo["secrets"]], ["AWS access key"])
        again = self.run_stream("/repos", {"project_id": self.project, "url": url})
        self.assertFalse(again["data"]["changed"])  # same commit: no second download
        self.assertEqual(len(self.clones), 1)
        self.head = "a-newer-commit-on-the-remote"
        self.assertTrue(self.run_stream("/repos", {"project_id": self.project, "url": url})["data"]["changed"])
        self.assertEqual(len(self.clones), 2)
        card = self.client.get(self.base + "/overview").json()[0]
        self.assertIn("mongodb", card["unsupported"])  # claimed on the resume, absent from the code
        self.assertIn("postgresql", card["undeclared"])  # in the code, missing from the resume
        who = self.client.put(f"{self.base}/repos/{self.project}/identity", json={"identities": ["asha@example.com"]}).json()
        self.assertTrue(who["ownership"]["identified"])
        self.assertEqual(self.client.delete(f"{self.base}/repos/{self.project}").json(), {"removed": True})
        self.assertIsNone(self.client.get(self.base + "/overview").json()[0]["repo"])

    def test_bad_urls_are_rejected_before_anything_runs(self):
        for bad in ("http://github.com/a/b", "https://evil.com/a/b", "file:///etc", "https://github.com/a/b/../../c", "git@github.com:a/b.git", "https://github.com/a"):
            result = self.run_stream("/repos", {"project_id": self.project, "url": bad})
            self.assertEqual(result["type"], "error", bad)
        self.assertEqual(self.clones, [])

    def test_signals_study_first_and_blast_radius(self):
        signals = self.client.get(self.base + "/signals").json()
        self.assertIsNone(signals["overall"])
        top = signals["topics"][0]
        self.assertFalse(top["assessed"])
        self.assertGreater(top["risk"], 0)
        self.assertTrue(any("Not assessed" in w for w in top["why"]))
        queue = self.client.get(self.base + "/study-first", params={"limit": 3}).json()
        self.assertEqual(len(queue), 3)
        self.assertEqual(queue[0]["topic"], top["topic"])
        blast = self.client.get(self.base + "/blast", params={"topic": "Database fundamentals"}).json()
        self.assertIn("Shop", blast["projects"])
        self.assertEqual(self.client.get(self.base + "/blast", params={"topic": "Nonsense"}).status_code, 404)

    def test_evidence_moves_readiness_and_lowers_risk(self):
        from core.schemas import Feedback
        from core.review import Reviews
        signals = {t["topic"]: t for t in self.client.get(self.base + "/signals").json()["topics"]}
        topic = "Database fundamentals"
        risk_before = signals[topic]["risk"]
        score = lambda n: {"score": n, "reason": "r"}
        fb = Feedback(accuracy=score(4), coverage=score(4), reasoning=score(3), clarity=score(4), correct="c", missing="m", corrected="x", follow_up="f",
                      learning_metadata={"independent": True})
        record = self.core.store.get(self.pid)
        self.core.store.save_attempt(record, "a1", f"{topic} · Basics", "Q?", "A", fb)
        Reviews(self.core.store).rate(self.pid, f"skill:Basics:{topic}", "Q?", "A", "h", "Easy")
        after = {t["topic"]: t for t in self.client.get(self.base + "/signals").json()["topics"]}[topic]
        self.assertTrue(after["assessed"])
        self.assertGreater(after["readiness"], 7)
        self.assertLess(after["risk"], risk_before)
        self.assertEqual(self.client.get(self.base + "/signals").json()["assessed"], 1)
        Reviews(self.core.store).rate(self.pid, f"skill:Basics:{topic}", "Q?", "A", "h", "Again")  # forgetting it pulls readiness down
        lapsed = {t["topic"]: t for t in self.client.get(self.base + "/signals").json()["topics"]}[topic]
        self.assertLess(lapsed["readiness"], after["readiness"])
        self.assertGreater(lapsed["readiness"], 5)  # one forgotten card lowers the score but does not wreck a strong topic


class ClaimsAndSummaryTests(ApiTests):
    """Reuses ApiTests.setUp (a real fixture git repository, fake clone) with extra checks."""

    test_repo_lifecycle_is_incremental_and_never_leaks_secrets = test_bad_urls_are_rejected_before_anything_runs = None
    test_signals_study_first_and_blast_radius = test_evidence_moves_readiness_and_lowers_risk = None

    def test_claim_tiers_follow_the_evidence(self):
        before = {(r["technology"]): r for r in self.client.get(self.base + "/claims").json()}
        self.assertEqual({r["tier"] for r in before.values()}, {"Unchecked"})  # no repo attached yet
        self.run_stream("/repos", {"project_id": self.project, "url": "https://github.com/asha/shop"})
        rows = {r["technology"]: r for r in self.client.get(self.base + "/claims").json()}
        self.assertEqual((rows["react"]["tier"], rows["react"]["confidence"]), ("High", 0.9))
        self.assertEqual(rows["express"]["tier"], "High")
        self.assertEqual(rows["mongodb"]["tier"], "Low")
        self.assertTrue(rows["react"]["evidence"])
        ordered = [r["tier"] for r in self.client.get(self.base + "/claims").json()]
        self.assertEqual(ordered, sorted(ordered, key=["Low", "Unchecked", "Medium", "High"].index))  # weakest evidence first
        self.assertIsNotNone(rows["mongodb"]["weakest_concept"])

    def test_summary_counts_and_days_to_interview(self):
        from datetime import date, timedelta
        s = self.client.get(self.base + "/summary").json()
        self.assertEqual((s["readiness"]["overall"], s["mastered"], s["repos"], s["projects"]), (None, 0, 0, 1))
        self.assertEqual(s["high_risk"], 0)  # one project's unknown topics are medium risk, not alarming
        self.assertGreaterEqual(self.client.get(self.base + "/signals").json()["topics"][0]["risk"], 3)
        for title in ("Blog", "Chat"):  # the same stack in three projects makes its topics likely to come up
            rev = self.client.get(f"/api/profiles/{self.pid}").json()["revision"]
            self.client.post(f"/api/profiles/{self.pid}/projects", json={"revision": rev, "title": title, "technologies": ["React.js", "Express.js", "MongoDB"]})
        self.assertGreater(self.client.get(self.base + "/summary").json()["high_risk"], 0)
        self.assertEqual(len(s["study_first"]), 5)
        self.assertIsNone(s["days_to_interview"])
        settings = self.client.get(f"/api/profiles/{self.pid}/learning/settings").json()["settings"]
        when = (date.today() + timedelta(days=9)).isoformat()
        self.client.put(f"/api/profiles/{self.pid}/learning/settings", json=settings | {"interview": when})
        self.assertEqual(self.client.get(self.base + "/summary").json()["days_to_interview"], 9)
        self.client.put(f"/api/profiles/{self.pid}/learning/settings", json=settings | {"interview": "2020-01-01"})
        self.assertIsNone(self.client.get(self.base + "/summary").json()["days_to_interview"])  # past dates are ignored



class SecurityTests(ApiTests):
    test_repo_lifecycle_is_incremental_and_never_leaks_secrets = test_bad_urls_are_rejected_before_anything_runs = None
    test_signals_study_first_and_blast_radius = test_evidence_moves_readiness_and_lowers_risk = None

    def test_questions_follow_stack_and_findings(self):
        from core.career import security
        q = security.questions(["jwt", "postgresql", "docker"], has_secrets=True)
        self.assertIn("leaked", q[0])
        self.assertTrue(any("token" in x.lower() for x in q) and any("SQL injection" in x for x in q))
        self.assertLessEqual(len(q), 8)
        self.assertEqual(len(set(q)), len(q))
        self.assertEqual(security.questions([], False), security.GENERAL)

    def test_security_endpoint_masks_secrets_and_covers_projects_without_repos(self):
        before = self.client.get(self.base + "/security").json()
        self.assertEqual([(p["has_repo"], p["secrets"]) for p in before["projects"]], [(False, [])])
        self.assertTrue(any("React" in q or "cross-site" in q for q in before["projects"][0]["questions"]))  # from the resume stack alone
        self.run_stream("/repos", {"project_id": self.project, "url": "https://github.com/asha/shop"})
        after = self.client.get(self.base + "/security").json()
        project = after["projects"][0]
        self.assertEqual([s["kind"] for s in project["secrets"]], ["AWS access key"])
        self.assertNotIn(FAKE_AWS, json.dumps(after))
        self.assertIn("leaked", project["questions"][0])
        self.assertEqual(len(after["remediation"]), 3)


class DecisionTests(ApiTests):
    test_repo_lifecycle_is_incremental_and_never_leaks_secrets = test_bad_urls_are_rejected_before_anything_runs = None
    test_signals_study_first_and_blast_radius = test_evidence_moves_readiness_and_lowers_risk = None

    def setUp(self):
        super().setUp()
        self.model = self.core.settings.model
        self.sha = None
        from core.schemas import DecisionSet
        def fake(kind, context, schema, validate=None, progress=None):
            if kind == "decisions":
                ref = self.cite or context["candidates"]["commits"][0]["sha"]
                result = DecisionSet(decisions=[{"title": "Added a cache", "decision": "Cached hot lookups.", "alternatives": ["No cache"],
                                                 "evidence": [{"kind": "commit", "ref": ref}], "tradeoff_question": "Why a cache?",
                                                 "answer": "To cut latency. (Assumption) it was reads.", "confidence": "medium", "assumption": "Reason inferred."}])
                if validate:
                    validate(result)
                return result, self.model
            from core.schemas import ProjectLesson
            q = [{"question": f"Q{n}?", "answer": "A.", "hint": "h"} for n in range(6)]
            lesson = ProjectLesson(prerequisites=["x"], terms=["t"], explanation="e", example="x", project_application="p", questions=q, follow_ups=q[:2], exercise="x", assumptions="a")
            self.contexts.append(context)
            return lesson, self.model
        self.contexts, self.cite = [], None
        patcher = patch.object(self.core.service, "generate", side_effect=fake)
        patcher.start(); self.addCleanup(patcher.stop)
        # give the fixture history a decision-sounding commit
        for name, text in (("src/cache.js", "export const cache = new Map();\n"),):
            (self.fixture / name).write_text(text)
        subprocess.run(["git", "-C", str(self.fixture), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.fixture), "-c", "user.name=Asha", "-c", "user.email=asha@example.com", "commit", "-qm", "Add Redis cache to speed up lookups"], check=True, capture_output=True)
        self.head_value = repo_mod.head_commit(self.fixture)
        self.head = self.head_value

    def attach(self):
        return self.run_stream("/repos", {"project_id": self.project, "url": "https://github.com/asha/shop"})

    def test_candidates_are_real_and_decisions_must_cite_them(self):
        from core.career import decisions
        found = decisions.candidates(self.fixture, ["asha@example.com"], ["express", "redis"])
        self.assertEqual(found["commits"][0]["subject"], "Add Redis cache to speed up lookups")
        self.assertTrue(found["commits"][0]["yours"])
        self.assertIn(found["commits"][0]["sha"], decisions.allowed_refs(found))
        self.assertEqual(self.client.get(f"{self.base}/../artifacts/decisions", params={"project_id": self.project}).status_code, 400)  # no repo yet: friendly error
        self.attach()
        base = f"/api/profiles/{self.pid}/artifacts/decisions"
        out = [json.loads(l) for l in self.client.post(base + "/run", json={"project_id": self.project}).text.splitlines() if l][-1]
        self.assertEqual(out["type"], "result", out)
        self.assertEqual(out["data"]["status"], "current")
        self.assertEqual(out["data"]["data"]["decisions"][0]["evidence"][0]["kind"], "commit")
        self.assertIn("Added a cache", self.client.get(base + "/export", params={"project_id": self.project}).text)
        self.cite = "deadbee"  # a made-up commit id is rejected, not stored
        bad = [json.loads(l) for l in self.client.post(base + "/run", json={"project_id": self.project, "regenerate": True}).text.splitlines() if l][-1]
        self.assertEqual(bad["type"], "error")
        self.assertIn("not in the supplied", bad["message"])

    def test_repo_facts_reach_project_lessons_and_a_new_commit_makes_them_stale(self):
        ref = {"kind": "project", "project_id": self.project, "section": "Database"}
        url = f"/api/profiles/{self.pid}/lessons"
        first = [json.loads(l) for l in self.client.post(url + "/generate", json=ref).text.splitlines() if l][-1]["data"]
        self.assertNotIn("code", self.contexts[-1])  # no repository yet, so nothing extra is sent
        self.assertEqual(first["status"], "current")
        self.attach()
        self.assertEqual(self.client.get(url, params=ref).json()["status"], "outdated")  # attaching the repo changes what the lesson should know
        regen = [json.loads(l) for l in self.client.post(url + "/generate", json=ref | {"regenerate": True}).text.splitlines() if l][-1]["data"]
        self.assertEqual(regen["status"], "current")
        code = self.contexts[-1]["code"]
        self.assertEqual(code["repo"], "https://github.com/asha/shop")
        self.assertIn("express", code["stack"])
        self.assertNotIn("secrets", code)
        self.assertEqual(self.client.get(url, params=ref).json()["status"], "current")
        (self.fixture / "src" / "later.js").write_text("export const later = 1;\n" * 30)  # the repository moves on
        subprocess.run(["git", "-C", str(self.fixture), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.fixture), "-c", "user.name=Asha", "-c", "user.email=asha@example.com", "commit", "-qm", "later work"], check=True, capture_output=True)
        self.head = "force-refresh"
        self.attach()
        self.assertEqual(self.client.get(url, params=ref).json()["status"], "outdated")  # new commit: the page is stale


class WikiTests(DecisionTests):
    test_candidates_are_real_and_decisions_must_cite_them = test_repo_facts_reach_project_lessons_and_a_new_commit_makes_them_stale = None

    def test_wiki_lists_pages_with_freshness_and_reasons(self):
        rows = {(r["group"], r["title"]): r for r in self.client.get(self.base + "/wiki").json()}
        self.assertEqual(rows[("Shop", "Database")]["status"], "none")
        self.assertEqual(rows[("Shop", "Project pitch")]["kind"], "Project pitch")
        self.assertNotIn(("Shop", "Decisions from your code"), rows)  # no repo yet, nothing to mine
        ref = {"kind": "project", "project_id": self.project, "section": "Database"}
        self.client.post(f"/api/profiles/{self.pid}/lessons/generate", json=ref)
        db = {(r["group"], r["title"]): r for r in self.client.get(self.base + "/wiki").json()}[("Shop", "Database")]
        self.assertEqual((db["status"], db["model"] is not None), ("fresh", True))
        self.attach()  # attaching the repository changes what the page should know
        after = {(r["group"], r["title"]): r for r in self.client.get(self.base + "/wiki").json()}
        self.assertEqual(after[("Shop", "Database")]["status"], "stale")
        self.assertIn("repository", after[("Shop", "Database")]["why"])
        self.assertIn(("Shop", "Decisions from your code"), after)
        self.assertEqual(self.client.get(self.base + "/summary").json()["stale_pages"], 1)

    def test_refresh_rewrites_only_stale_pages_and_respects_the_cap(self):
        for section in ("Database", "Server side"):
            self.client.post(f"/api/profiles/{self.pid}/lessons/generate", json={"kind": "project", "project_id": self.project, "section": section})
        self.attach()
        calls = len(self.contexts)
        out = [json.loads(l) for l in self.client.post(self.base + "/wiki/refresh", json={"limit": 1}).text.splitlines() if l][-1]["data"]
        self.assertEqual((out["refreshed"], out["remaining"], len(self.contexts) - calls), (1, 1, 1))
        out = [json.loads(l) for l in self.client.post(self.base + "/wiki/refresh", json={"limit": 4}).text.splitlines() if l][-1]["data"]
        self.assertEqual((out["refreshed"], out["remaining"]), (1, 0))
        self.assertEqual(self.client.get(self.base + "/summary").json()["stale_pages"], 0)
        untouched = {(r["group"], r["title"]): r for r in self.client.get(self.base + "/wiki").json()}[("Shop", "Client side")]
        self.assertEqual(untouched["status"], "none")  # never generated pages are left alone


class CandidateQualityTests(unittest.TestCase):
    def test_maintenance_commits_are_not_decisions(self):
        from core.career import decisions
        for noise in ("ci: upgrade Node versions (#359)", "chore: bump express from 4 to 5", "Merge pull request #12", "docs: add cache section to README", "Extend CI test matrix"):
            self.assertFalse(decisions.KEYWORDS.search(noise) and not decisions.NOISE.search(noise), noise)
        for real in ("Switch from polling to Socket.io for order updates", "Add Redis cache to speed up lookups", "Replace sessions with JWT auth", "Migrate database from SQLite to Postgres"):
            self.assertTrue(decisions.KEYWORDS.search(real) and not decisions.NOISE.search(real), real)


class CitationTests(unittest.TestCase):
    def test_harmless_variants_are_accepted_and_stored_canonically_but_inventions_are_not(self):
        from core.career import decisions
        from core.material import decisions_request
        from core.schemas import DecisionSet, Profile, Project
        project = Project(title="Shop")
        found = {"commits": [{"sha": "98f2ef4", "subject": "Add cache", "yours": True}], "readme": "text", "dependencies": ["Redis"]}
        request = decisions_request(Profile(projects=[project]), project, found)
        def make(*refs):
            return DecisionSet(decisions=[{"title": "t", "decision": "d", "evidence": [{"kind": "commit", "ref": r} for r in refs], "tradeoff_question": "q", "answer": "a", "confidence": "low", "assumption": "inferred"}])
        ok = make("commit 98f2ef4", "README.md", "redis", "98F2EF4A9B8C7D6E5F4A3B2C1D0E9F8A7B6C5D4E")
        self.assertEqual(request.validate(ok), None)
        self.assertEqual([e.ref for e in ok.decisions[0].evidence], ["98f2ef4", "README", "redis", "98f2ef4"])
        self.assertEqual(decisions.canonical_ref("SHA: ABCDEF1234"), "abcdef1")
        for invented in ("deadbee", "package.json", "https://github.com/x/y"):
            with self.assertRaises(ValueError):
                request.validate(make(invented))

    def test_the_retry_tells_the_model_what_was_wrong(self):
        from types import SimpleNamespace
        from core.config import Settings
        from core.llm import ModelService
        from core.schemas import ProfileDraft
        service = ModelService(Settings(api_key="k", fast_model=""))
        reply = lambda body: SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=body))])
        with patch("core.llm.Groq") as client:
            call = client.return_value.__enter__.return_value.chat.completions.create
            call.side_effect = [reply('{"name": 5}'), reply("{}")]
            service.generate("profile", {"reviewed_resume": "x"}, ProfileDraft)
        retry = call.call_args_list[1].kwargs["messages"][0]["content"]
        self.assertIn("Problem found:", retry)
        self.assertIn("name", retry)


class RetentionShrinkTests(ApiTests):
    test_repo_lifecycle_is_incremental_and_never_leaks_secrets = test_bad_urls_are_rejected_before_anything_runs = None
    test_signals_study_first_and_blast_radius = test_evidence_moves_readiness_and_lowers_risk = None

    def test_one_forgotten_flashcard_does_not_define_a_topic(self):
        from core.review import Reviews
        topic = "Database fundamentals"
        Reviews(self.core.store).rate(self.pid, f"skill:Basics:{topic}", "Q?", "A", "h", "Again")
        one = {t["topic"]: t for t in self.client.get(self.base + "/signals").json()["topics"]}[topic]
        self.assertTrue(one["assessed"])
        self.assertGreater(one["readiness"], 2.0)  # not floored to 1.0 by a single lapse
        for n in range(4):
            Reviews(self.core.store).rate(self.pid, f"skill:Basics:{topic}", f"Q{n}?", "A", "h", "Again")
        many = {t["topic"]: t for t in self.client.get(self.base + "/signals").json()["topics"]}[topic]
        self.assertLess(many["readiness"], one["readiness"])  # repeated lapses do pull it down


class HonestyRuleTests(unittest.TestCase):
    def make(self, **change):
        from core.material import decisions_request
        from core.schemas import DecisionSet, Profile, Project
        project = Project(title="Shop")
        found = {"commits": [{"sha": "98f2ef4", "subject": "Add Redis cache because lookups were slow", "yours": True}], "readme": "Uses Express.", "dependencies": ["redis"]}
        request = decisions_request(Profile(projects=[project]), project, found)
        base = {"title": "Cache", "decision": "d", "evidence": [{"kind": "commit", "ref": "98f2ef4", "quote": "lookups were slow"}], "tradeoff_question": "q", "answer": "a", "confidence": "high", "assumption": ""}
        return request, DecisionSet(decisions=[base | change])

    def check(self, **change):
        request, result = self.make(**change)
        request.validate(result)
        return result.decisions[0]

    def test_confidence_is_earned_not_claimed(self):
        from core.material import INFERRED
        kept = self.check()  # a real quote that states the reason: high confidence stands
        self.assertEqual((kept.confidence, kept.assumption, kept.evidence[0].quote), ("high", "", "lookups were slow"))
        for change in ({"evidence": [{"kind": "commit", "ref": "98f2ef4", "quote": ""}]},                       # no quote
                       {"evidence": [{"kind": "commit", "ref": "98f2ef4", "quote": "it sped everything up"}]}):  # a quote that is not in the commit
            d = self.check(**change)
            self.assertEqual((d.confidence, d.assumption, d.evidence[0].quote), ("medium", INFERRED, ""))
        self.assertEqual(self.check(confidence="low").assumption, INFERRED)  # a missing assumption is filled in
        own = self.check(confidence="medium", assumption="I chose it for speed.", evidence=[{"kind": "dependency", "ref": "redis"}])
        self.assertEqual((own.confidence, own.assumption), ("medium", "I chose it for speed."))  # the model's own assumption is kept

    def test_a_made_up_source_is_still_rejected(self):
        request, result = self.make(evidence=[{"kind": "commit", "ref": "deadbee", "quote": ""}])
        with self.assertRaisesRegex(ValueError, "not in the supplied"):
            request.validate(result)
