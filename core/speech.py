"""Validate bounded PCM WAV before hosted transcription. Audio is never written to disk."""
from io import BytesIO
import struct
import wave

from groq import Groq, APIConnectionError, APIStatusError, APIError
from core.llm import ModelError, retry_delay
import time


def validate_audio(data, settings):
    if not data or len(data) > settings.audio_mb * 1024**2:
        raise ValueError(f"Choose a nonempty WAV recording below {settings.audio_mb} MB.")
    try:
        with wave.open(BytesIO(data)) as audio:
            channels, width, rate, frames = audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()
            if width != 2 or channels not in (1, 2) or rate < 8000:
                raise ValueError("Use 16-bit PCM WAV, mono or stereo, at 8 kHz or higher.")
            if not frames or frames / rate > settings.audio_seconds:
                raise ValueError(f"Recording must be between 0 and {settings.audio_seconds} seconds.")
            samples = audio.readframes(frames)
            if len(samples) != frames * channels * width:
                raise ValueError("The WAV recording is incomplete.")
            if not any(abs(value[0]) > 30 for value in struct.iter_unpack("<h", samples)):
                raise ValueError("The recording is silent or too quiet. Record again or type your answer.")
    except (wave.Error, EOFError):
        raise ValueError("This audio is unreadable. Use a PCM WAV recording or type your answer.") from None


def transcribe(data, settings):
    validate_audio(data, settings)
    if not settings.api_key:
        raise ModelError("Set GROQ_API_KEY to transcribe, or type your answer.")
    with Groq(api_key=settings.api_key, timeout=30, max_retries=0) as client:
        for attempt in range(2):
            delay = 1
            try:
                result = client.audio.transcriptions.create(
                    model=settings.stt_model, file=("answer.wav", data, "audio/wav"),
                    language="en", response_format="json", temperature=0,
                )
                text = result.text.strip()
                if not text or len(text) > 3500:
                    raise ModelError("Transcription is empty or too long. Retry with a shorter recording or type your answer.")
                return text
            except APIConnectionError:
                error = ModelError("Transcription timed out or could not connect. Retry the saved recording or type your answer.")
            except APIStatusError as exc:
                status = exc.status_code
                if status in (401,403):
                    raise ModelError("Transcription access denied. Check the Groq key and permissions.") from None
                if status == 404:
                    raise ModelError("Transcription model unavailable. Check GROQ_STT_MODEL.") from None
                if status in (402,429):
                    raise ModelError("Transcription quota or rate limit reached. Wait for the provider reset or type your answer.") from None
                if status not in (408,409) and status < 500:
                    raise ModelError("Groq rejected the audio. Try another WAV recording or type your answer.") from None
                delay = retry_delay(exc.response.headers,1)
                error = ModelError("Transcription service temporarily unavailable. Your recording is retained for retry.")
            except APIError:
                raise ModelError("Transcription returned an unreadable result. Retry or type your answer.") from None
            if attempt or delay > 5:
                raise error
            time.sleep(delay)
