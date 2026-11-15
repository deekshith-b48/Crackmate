import io
import struct
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from core.config import Settings
from core.interview import Interviews, Session, Turn, PlannedQuestion, confirm, advance, evaluate, report
from core.schemas import Profile, Feedback
from core.speech import validate_audio, transcribe
from core.storage import Storage
from streamlit.testing.v1 import AppTest


def feedback():
    score={"score":3,"reason":"Specific example"}
    return Feedback(accuracy=score,coverage=score,reasoning=score,clarity=score,
                    correct="Defined the concept.",missing="Failure handling.",corrected="Handle transient failures.",
                    follow_up="How would you handle a timeout?")


def wav(value=500):
    buffer=io.BytesIO()
    with wave.open(buffer,"wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(struct.pack("<h",value)*16000)
    return buffer.getvalue()


class InterviewTests(unittest.TestCase):
    def setUp(self):
        directory=TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store=Storage(Path(directory.name)/"db")
        self.record=self.store.create(Profile())
        self.repo=Interviews(self.store)
        self.session=self.repo.create(Session(
            profile_id=self.record.id,mode="Technical fundamentals",topic="Networking",
            difficulty="Basics",budget=2,coach=False,
            turns=[Turn(question=PlannedQuestion(question=f"Question {n}?",answer="Reference",hint="Define the concept")) for n in range(2)]
        ))

    def test_confirmed_transcript_evaluation_recovery_and_followup(self):
        self.session.turns[0].original="incorrect recognition"
        confirm(self.session,"Corrected technical answer")
        self.session=self.repo.save(self.session)
        service=Mock()
        service.generate.return_value=(feedback(),"test")
        result=evaluate(self.repo,service,self.record,self.session,lambda _:None)
        self.assertEqual(service.generate.call_args.args[1]["candidate_answer"],"Corrected technical answer")
        self.assertEqual(self.repo.get(result.id,self.record.id).state,"feedback ready")
        evaluate(self.repo,service,self.record,self.session,lambda _:None)
        self.assertEqual(service.generate.call_count,1)
        advance(result,follow=True)
        self.assertEqual(result.turns[1].depth,1)
        advance(result,skip=True)
        self.assertEqual(result.state,"completed")
        self.assertIn("1 scored questions",report(result))
        self.assertIn("Skipped 1",report(result))
        self.assertIn("Corrected technical answer",report(result))
        self.store.delete(self.record.id)
        self.assertEqual(self.repo.list(self.record.id),[])

    def test_audio_validation(self):
        validate_audio(wav(),Settings())
        for data in (b"",b"invalid",wav(0),b"x"*(1024*1024+1)):
            with self.assertRaises(ValueError):
                validate_audio(data,Settings(audio_mb=1))

    def test_transcription_failure_retry(self):
        from groq import APIConnectionError
        from httpx import Request
        client=Mock()
        client.audio.transcriptions.create.side_effect=[
            APIConnectionError(request=Request("POST","https://api.groq.com")),
            Mock(text="Recognised answer"),
        ]
        with patch("core.speech.Groq") as groq, patch("core.speech.time.sleep"):
            groq.return_value.__enter__.return_value=client
            self.assertEqual(transcribe(wav(),Settings(api_key="test")),"Recognised answer")

    def test_simulation_feedback_hidden(self):
        self.session.turns[0].feedback=feedback()
        self.session.turns[0].confirmed="Answer"
        self.session.turns[0].outcome="answered"
        self.session.state="feedback ready"
        self.repo.save(self.session)
        settings=Settings(database=self.store.path)
        with patch("core.config.Settings.load",return_value=settings):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/"app.py")).run()
            next(w for w in app.radio if w.label=="Go to").set_value("Interview Room").run()
            self.assertFalse(app.exception)
            self.assertNotIn("Handle transient failures.",str([m.value for m in app.markdown]))
            self.assertTrue(any(b.label=="Next question" for b in app.button))


    def test_typed_confirmation_and_evaluation_from_ui(self):
        settings=Settings(database=self.store.path,api_key="synthetic")
        with patch("core.config.Settings.load",return_value=settings), patch("core.llm.ModelService.generate",return_value=(feedback(),"test")) as model:
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/"app.py")).run()
            next(w for w in app.radio if w.label=="Go to").set_value("Interview Room").run()
            next(w for w in app.text_area if w.label=="Review transcript or type your answer").set_value("TCP provides reliable ordered bytes.")
            next(w for w in app.button if w.label=="Confirm answer").click().run()
            self.assertFalse(app.exception)
            next(w for w in app.button if w.label=="Evaluate confirmed answer").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(model.call_args.args[1]["candidate_answer"],"TCP provides reliable ordered bytes.")
            next(w for w in app.button if w.label=="Next question").click().run()
            self.assertFalse(app.exception)
