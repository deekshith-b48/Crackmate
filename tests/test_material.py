from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from core.material import Material, project_request, skill_request
from core.schemas import Profile, Project, SkillLesson
from core.storage import Storage


def skill_lesson():
    return SkillLesson(
        prerequisites=["Variables"], explanation="A dict maps keys to values.",
        example="Use a dict to count requests by path.", mistakes=["Mutable keys"],
        questions=[{"question": f"Question {n}?", "answer": "An answer.", "hint": "Start with the definition."} for n in range(5)],
        exercise="Count repeated paths."
    )


class MaterialTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Storage(Path(directory.name) / "test.sqlite3")
        self.record = self.store.create(Profile(projects=[Project(title="API", contribution="Routing")]))
        self.model = Mock()
        self.model.settings.model = "test-model"
        self.model.settings.fallback_model = ""
        self.model.temperature = 0.2
        self.model.generate.return_value = (skill_lesson(), "test-model")
        self.material = Material(self.store, self.model)

    def test_reuse_regenerate_and_outdated(self):
        request = skill_request(self.record.profile, "Networking", "Basics")
        item, fresh = self.material.generate(self.record, request)
        self.assertTrue(fresh)
        self.assertEqual(self.material.generate(self.record, request), (item, False))
        self.model.generate.assert_called_once()
        self.material.generate(self.record, request, regenerate=True)
        self.assertEqual(self.model.generate.call_count, 2)
        edited = self.store.save(self.record, self.record.profile.model_copy(update={"role": "Backend"}))
        changed = skill_request(edited.profile, "Networking", "Basics")
        self.assertFalse(self.material.current(edited, changed, item))
        self.model.generate.side_effect = RuntimeError("offline")
        reloaded, fresh = self.material.generate(edited, changed)  # the shared cache answers without the model
        self.assertFalse(fresh)
        self.assertTrue(self.material.current(edited, changed, reloaded))
        with self.assertRaisesRegex(RuntimeError, "offline"):
            self.material.generate(edited, changed, regenerate=True, tailor=True)
        self.assertEqual(self.store.item(edited.id, changed.slot).body, item.body)
        self.store.delete(edited.id)
        self.assertIsNone(self.store.item(edited.id, changed.slot))

    def test_corrected_project_is_sent_as_relevant_context(self):
        project = self.record.profile.projects[0]
        corrected = project.model_copy(update={"contribution": "Implemented caching"})
        updated = self.store.save(self.record, Profile(projects=[corrected], name="Private Name"))
        request = project_request(updated.profile, corrected, "Server side")
        self.assertEqual(request.context["project"]["contribution"], "Implemented caching")
        self.assertNotIn("Private Name", str(request.context))
        self.assertEqual(request.slot, project_request(self.record.profile, project, "Server side").slot)


class SharedCacheTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Storage(Path(directory.name) / "test.sqlite3")
        self.model = Mock()
        self.model.settings.model, self.model.settings.fallback_model, self.model.temperature = "m", "", 0.2
        self.model.generate.return_value = (skill_lesson(), "m")
        self.material = Material(self.store, self.model)

    def test_second_profile_reuses_lesson_without_model_and_keeps_private_data_out(self):
        a = self.store.create(Profile(role="Backend", projects=[Project(title="Secret API", contribution="Routing")]))
        b = self.store.create(Profile(role="Frontend"))
        request_a = skill_request(a.profile, "Networking", "Basics")
        self.material.generate(a, request_a)
        sent = self.model.generate.call_args.args[1]
        self.assertNotIn("Secret API", str(sent))
        self.assertEqual(sent["target"], {})
        request_b = skill_request(b.profile, "Networking", "Basics")
        self.assertIsNotNone(self.material.shared_body(request_b))
        item, fresh = self.material.generate(b, request_b)
        self.assertFalse(fresh)
        self.model.generate.assert_called_once()
        self.assertTrue(self.material.current(b, request_b, item))

    def test_tailored_lesson_stays_private_and_projects_are_never_shared(self):
        a = self.store.create(Profile(projects=[Project(title="API")]))
        request = skill_request(a.profile, "Networking", "Basics")
        self.material.generate(a, request, tailor=True)
        self.assertEqual(self.material.cache.count(), 0)
        self.assertIn("candidate_stack", self.model.generate.call_args.args[1])
        self.material.generate(a, project_request(a.profile, a.profile.projects[0], "Database"))
        self.assertEqual(self.material.cache.count(), 0)

    def test_warm_fills_cache_once(self):
        request = skill_request(Profile(), "Caching", "Basics")
        self.assertTrue(self.material.warm(request))
        self.assertFalse(self.material.warm(request))
        self.model.generate.assert_called_once()
        self.assertEqual(self.material.cache.count(), 1)

    def test_fifty_distinct_pregen_topics(self):
        from core.pregen import PREGEN_TOPICS
        self.assertEqual((len(PREGEN_TOPICS), len(set(PREGEN_TOPICS))), (50, 50))


class PatientWarmTests(unittest.TestCase):
    def test_waits_out_rate_limits_then_succeeds_and_gives_up_on_other_errors(self):
        from unittest.mock import patch
        from core.llm import ModelError
        from core.pregen import warm_patiently
        material = Mock()
        material.warm.side_effect = [ModelError("slow down", try_next=True, retry_after=12), ModelError("again", try_next=True), True]
        with patch("core.pregen.time.sleep") as sleep:
            self.assertTrue(warm_patiently(material, "r"))
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [12, 30])
        material.warm.side_effect = ModelError("daily budget", try_next=True, retry_after=757)  # too long to wait
        with patch("core.pregen.time.sleep") as sleep, self.assertRaises(ModelError):
            warm_patiently(material, "r")
        sleep.assert_not_called()
        material.warm.side_effect = ModelError("bad key")  # not a rate limit: no retry
        with patch("core.pregen.time.sleep") as sleep, self.assertRaises(ModelError):
            warm_patiently(material, "r")
        sleep.assert_not_called()
