from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import asyncio
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from test_career import make_repo  # noqa: E402
from test_material import skill_lesson  # noqa: E402

from api.deps import Core, wire
from core.config import Settings
from core.llm import ModelService
from core.material import Material, skill_request
from core.review import Reviews
from core.schemas import Feedback, Profile, ProfileDraft, Project
from core.storage import Storage
from crackmate import tools
from crackmate.__main__ import main
from crackmate.mcp_server import build_server

SCORE = lambda n: {"score": n, "reason": "r"}
FEEDBACK = Feedback(accuracy=SCORE(3), coverage=SCORE(2), reasoning=SCORE(3), clarity=SCORE(4), correct="Good.", missing="Add trade-offs.", corrected="Better.", follow_up="What if it fails?")


class Base(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = Settings(api_key="synthetic", database=self.root / "t.sqlite3")
        store = Storage(settings.database)
        service = ModelService(settings)
        self.core = wire(Core(settings, store, service, Material(store, service)))
        self.record = store.create(Profile(name="Asha", role="Backend", summary="Reach me at asha@example.com",
                                           projects=[Project(title="Order Tracker", technologies=["Redis", "PostgreSQL", "Express.js"])]))
        self.lines, self.answers = [], []
        self.model = settings.model

    def cli(self, *argv):
        code = main(list(argv), core_factory=lambda: self.core, out=self.lines.append, read=lambda prompt="": self.answers.pop(0) if self.answers else "q")
        return code, "\n".join(self.lines)

    def with_lesson(self):
        with patch.object(self.core.service, "generate", return_value=(skill_lesson(), self.model)):
            self.core.material.generate(self.record, skill_request(self.record.profile, "Caching", "Basics"))


class CliTests(Base):
    def test_profiles_risk_next_and_brief(self):
        code, text = self.cli("profiles")
        self.assertEqual(code, 0)
        self.assertIn("Asha", text)
        self.lines.clear()
        code, text = self.cli("risk", "-n", "3")
        self.assertEqual(code, 0)
        self.assertIn("RISK /10", text)
        self.assertIn("not assessed", text)
        self.assertEqual(len([l for l in text.splitlines() if "not assessed" in l]), 3)
        self.lines.clear()
        self.assertIn("Study first:", self.cli("next")[1])
        self.lines.clear()
        out = self.root / "brief.md"
        self.assertEqual(self.cli("brief", "-o", str(out))[0], 0)
        brief = out.read_text()
        self.assertIn("# Interview brief: Asha", brief)
        self.assertNotIn("asha@example.com", brief)  # contacts are redacted

    def test_no_profile_and_bad_profile_give_friendly_errors(self):
        self.core.store.delete(self.record.id)
        code, text = self.cli("risk")
        self.assertEqual(code, 1)
        self.assertIn("No profile yet", text)
        self.lines.clear()
        self.core.store.create(Profile(name="B"))
        code, text = self.cli("risk", "--profile", "zzzz")
        self.assertEqual((code, "No single profile" in text), (1, True))

    def test_quiz_rates_cards_with_spaced_repetition_and_resolves_topic_names(self):
        self.with_lesson()
        self.answers = ["", "3", "", "1"]  # reveal + Good, reveal + Again
        code, text = self.cli("quiz", "--topic", "caching", "-n", "2")
        self.assertEqual(code, 0)
        self.assertIn("Next review in 1 day(s).", text)
        self.assertIn("Due again today.", text)
        due = Reviews(self.core.store).due(self.record.id)
        self.assertEqual(len(due), 1)  # the Again card is due today; the Good card is not
        self.lines.clear()
        self.answers = ["", "q"]
        self.cli("quiz", "--topic", "caching")
        self.assertIn("(due)", "\n".join(self.lines))  # due cards come first next time

    def test_quiz_with_nothing_available_and_unknown_topic(self):
        code, text = self.cli("quiz", "--topic", "Caching")
        self.assertIn("No questions available", text)
        self.lines.clear()
        code, text = self.cli("quiz", "--topic", "cach")
        self.assertEqual(code, 1)
        self.assertIn("Did you mean", text)

    def test_init_needs_consent_then_builds_profile_and_attaches_a_repo(self):
        fixture = make_repo(self.root / "fixture")
        resume = self.root / "resume.txt"
        resume.write_text("Asha Rao. Built Order Tracker with Redis.")
        draft = ProfileDraft(name="Asha Rao", projects=[{"title": "Order Tracker", "technologies": ["Redis"]}])
        with patch.object(self.core.service, "generate", return_value=(draft, self.model)) as model:
            self.answers = ["n"]
            code, text = self.cli("init", "--resume", str(resume))
            self.assertEqual((code, "Nothing was sent" in text), (1, True))
            model.assert_not_called()  # declined: the resume never left the machine
            self.lines.clear()
            clone = lambda url, dest: shutil.copytree(fixture, dest)
            from core.career import repo as repo_mod
            real_head = repo_mod.head_commit(fixture)
            with patch("core.career.repo.clone", clone), patch("core.career.repo.remote_head", lambda url: real_head), patch("core.career.repo.REPOS", self.root / "repos"):
                code, text = self.cli("init", "--resume", str(resume), "--yes", "--role", "Backend", "--repo", "https://github.com/asha/order-tracker")
                self.assertEqual(code, 0, text)
                self.assertIn("Created profile", text)
                self.assertIn("lines; stack:", text)
                newest = tools.resolve_profile(self.core)
                self.assertEqual((newest.profile.name, newest.profile.role), ("Asha Rao", "Backend"))
                self.assertEqual(tools.update_repos(self.core, newest), [{"url": "https://github.com/asha/order-tracker", "changed": False}])  # same commit: nothing re-read

    def test_init_rejects_missing_files_and_ambiguous_repos(self):
        self.assertIn("Cannot find", self.cli("init", "--resume", "nope.pdf", "--yes")[1])
        self.lines.clear()
        profile = self.core.store.create(Profile(projects=[Project(title="A"), Project(title="B")]))
        from crackmate.__main__ import attach
        from crackmate.tools import CrackError
        with self.assertRaisesRegex(CrackError, "Which project"):
            attach(self.core, profile, "https://github.com/x/unrelated", "", lambda _: None)


class ToolTests(Base):
    def test_lessons_never_call_a_model_and_questions_hide_answers(self):
        self.assertFalse(tools.lesson(self.core, self.record, "Caching")["available"])
        self.with_lesson()
        with patch.object(self.core.service, "generate", side_effect=AssertionError("no model call allowed")), patch.object(self.core.service, "stream", side_effect=AssertionError):
            lesson = tools.lesson(self.core, self.record, "caching")
            quiz = tools.quiz_me(self.core, self.record, "Caching", 3)
        self.assertTrue(lesson["available"] and lesson["questions"])
        self.assertEqual(len(quiz), 3)
        self.assertNotIn("answer", json.dumps(quiz))
        with self.assertRaises(tools.CrackError):
            tools.lesson(self.core, self.record, "Caching", "Expert")

    def test_grade_answer_scores_saves_an_attempt_and_moves_readiness(self):
        self.with_lesson()
        qid = tools.quiz_me(self.core, self.record, "Caching", 1)[0]["id"]
        with patch.object(self.core.service, "generate", return_value=(FEEDBACK.model_copy(deep=True), self.model)) as model:
            result = tools.grade_answer(self.core, self.record, qid, "A cache keeps hot data in memory.")
        model.assert_called_once()
        self.assertEqual(result["scores"], {"accuracy": 3, "coverage": 2, "reasoning": 3, "clarity": 4})
        self.assertEqual(len(self.core.store.attempts(self.record.id)), 1)
        for bad in ("", "x" * 3501):
            with self.assertRaises(tools.CrackError):
                tools.grade_answer(self.core, self.record, qid, bad)
        with self.assertRaisesRegex(tools.CrackError, "Unknown question id"):
            tools.grade_answer(self.core, self.record, "0" * 16, "an answer")

    def test_architecture_and_search(self):
        self.assertFalse(tools.architecture(self.core, self.record, "order")["available"])
        with self.assertRaises(tools.CrackError):
            tools.architecture(self.core, self.record, "nonexistent")
        self.assertEqual(tools.search_knowledge(self.core, self.record, "zzzxxqq"), [])
        self.assertTrue(tools.search_knowledge(self.core, self.record, "Redis PostgreSQL"))  # found in the resume project passage


class McpTests(Base):
    def test_server_exposes_the_ten_tools_and_returns_json(self):
        server = build_server(lambda: self.core)
        async def go():
            names = sorted(t.name for t in await server.list_tools())
            result = await server.call_tool("get_weak_spots", {"n": 2})
            return names, result
        names, result = asyncio.run(go())
        self.assertEqual(names, ["get_interview_brief", "get_lesson", "get_overview", "get_profile", "get_project_architecture",
                                 "get_study_next", "get_weak_spots", "grade_answer", "quiz_me", "search_knowledge"])
        payload = json.loads(result.content[0].text) if not isinstance(json.loads(result.content[0].text), dict) else json.loads(result.content[0].text)
        self.assertTrue(payload)
        profile = json.loads(asyncio.run(build_server(lambda: self.core).call_tool("get_profile", {})).content[0].text)
        self.assertNotIn("asha@example.com", json.dumps(profile))

    def test_real_stdio_protocol_round_trip(self):
        """Spawn the server exactly as a host would, then talk to it with the official MCP client."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        env = {**os.environ, "CRACKMATE_DB": str(self.core.settings.database)}
        params = StdioServerParameters(command=sys.executable, args=["-m", "crackmate", "mcp"], env=env, cwd=str(Path(__file__).resolve().parent.parent))
        async def go():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_ = await session.list_tools()
                    nxt = await session.call_tool("get_study_next", {})
                    bad = await session.call_tool("get_lesson", {"topic": "Not A Topic"})
                    return [t.name for t in tools_.tools], nxt, bad
        names, nxt, bad = asyncio.run(asyncio.wait_for(go(), 60))
        self.assertIn("quiz_me", names)
        self.assertIn("topic", json.loads(nxt.content[0].text))
        self.assertTrue(bad.is_error)  # a mistake is reported as a tool error, not a crash
        self.assertIn("Unknown topic", bad.content[0].text)
