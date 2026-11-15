"""Startup configuration. Environment variables override Streamlit secrets."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping

from core.resume import Limits


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_FAST_MODEL = "openai/gpt-oss-20b"


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="", repr=False)
    model: str = DEFAULT_MODEL
    fallback_model: str = ""
    fast_model: str = DEFAULT_FAST_MODEL  # empty string turns routing off
    stt_model: str = "whisper-large-v3-turbo"
    # Optional second provider (any OpenAI-compatible endpoint: Cerebras, Mistral, OpenRouter...) used when Groq is rate limited.
    alt_api_key: str = field(default="", repr=False)
    alt_base_url: str = ""
    alt_model: str = ""
    audio_mb: int = 10
    audio_seconds: int = 180
    limits: Limits = Limits()
    database: Path = ROOT / ".crackmate" / "preparation.sqlite3"

    @classmethod
    def load(cls, secrets: Mapping) -> "Settings":
        def setting(name, default=""):
            return str(os.environ.get(name, secrets.get(name, default))).strip()

        def integer(name, default, maximum):
            try:
                value = int(setting(name, default))
                if 1 <= value <= maximum:
                    return value
            except ValueError:
                pass
            raise ValueError(f"Set {name} to a whole number between 1 and {maximum}.")

        return cls(
            api_key=setting("GROQ_API_KEY"),
            model=setting("GROQ_MODEL") or DEFAULT_MODEL,
            fallback_model=setting("GROQ_FALLBACK_MODEL"),
            fast_model=setting("GROQ_FAST_MODEL", DEFAULT_FAST_MODEL),
            stt_model=setting("GROQ_STT_MODEL") or "whisper-large-v3-turbo",
            alt_api_key=setting("ALT_LLM_API_KEY"),
            alt_base_url=setting("ALT_LLM_BASE_URL"),
            alt_model=setting("ALT_LLM_MODEL"),
            audio_mb=integer("CRACKMATE_AUDIO_MB", 10, 24),
            audio_seconds=integer("CRACKMATE_AUDIO_SECONDS", 180, 600),
            limits=Limits(
                file_bytes=integer("CRACKMATE_MAX_FILE_MB", 5, 50) * 1024**2,
                pages=integer("CRACKMATE_MAX_PAGES", 10, 100),
                text_chars=integer("CRACKMATE_MAX_TEXT_CHARS", 12_000, 40_000),
            ),
        )
