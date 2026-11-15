"""One place that turns core exceptions into friendly messages. Replaces App.action in the Streamlit UI."""
import logging
import sqlite3

from pydantic import ValidationError

from core.llm import ModelError
from core.storage import StorageError

log = logging.getLogger("crackmate.api")


class NotFound(LookupError):
    pass


def describe(exc):
    """Return (http_status, message). Never leaks internals for unexpected errors."""
    if isinstance(exc, ValidationError):
        return 422, "Some fields are incomplete or exceed their limits. Check your entries and try again."
    if isinstance(exc, sqlite3.Error):
        return 500, "CrackMate could not read or save local data. Check disk permissions and try again."
    if isinstance(exc, LookupError):
        return 404, str(exc) or "That item no longer exists."
    if isinstance(exc, ModelError):
        message = str(exc)
        if exc.try_next and exc.retry_after > 5:  # tell people how long Groq asked them to wait
            message += f" Groq asks you to wait about {max(1, round(exc.retry_after / 60))} minute(s)."
        return (503 if exc.unavailable else 502), message
    if isinstance(exc, StorageError):
        return 409, str(exc)
    if isinstance(exc, ValueError):
        return 400, str(exc)
    log.exception("Unexpected error", exc_info=exc)
    return 500, "Something went wrong. Your saved work is safe. Please try again."
