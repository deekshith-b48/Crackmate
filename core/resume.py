"""Read uploads as data. LaTeX is never compiled."""
from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path

from pypdf import PdfReader


# Parser diagnostics can contain snippets of malformed uploaded content.
pdf_log = logging.getLogger("pypdf")
pdf_log.addHandler(logging.NullHandler())
pdf_log.propagate = False


class ResumeError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    file_bytes: int = 5 * 1024 * 1024
    pages: int = 10
    text_chars: int = 12_000


def reviewed_text(text: str, limits: Limits = Limits()) -> str:
    text = text.strip()
    if not text:
        raise ResumeError("The resume is empty. Paste text or upload a text-based PDF or LaTeX file.")
    if len(text) > limits.text_chars:
        raise ResumeError(f"The resume exceeds {limits.text_chars:,} characters. Paste a shorter excerpt.")
    return text


def read_upload(filename: str, data: bytes, limits: Limits = Limits()) -> str:
    if not data:
        raise ResumeError("The file is empty. Choose another file or paste your resume.")
    if len(data) > limits.file_bytes:
        raise ResumeError(f"The file is too large (limit {limits.file_bytes / 1024**2:g} MB).")
    suffix = Path(filename).suffix.lower()
    if suffix == ".tex":
        try:
            return reviewed_text(data.decode("utf-8-sig"), limits)
        except UnicodeDecodeError:
            raise ResumeError("Save the LaTeX source as UTF-8 or paste the text.") from None
    if suffix != ".pdf":
        raise ResumeError("Choose a PDF or LaTeX file.")
    if not data.startswith(b"%PDF-"):
        raise ResumeError("The file is unreadable as a PDF. Save a new PDF or use LaTeX or pasted text.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ResumeError("The PDF is encrypted. Upload an unlocked copy or paste the text.")
        if len(reader.pages) > limits.pages:
            raise ResumeError(f"The PDF exceeds the {limits.pages}-page limit.")
        parts = []
        size = 0
        for page in reader.pages:
            part = (page.extract_text() or "").strip()
            if part:
                size += len(part) + bool(parts)
                if size > limits.text_chars:
                    raise ResumeError(f"The PDF contains over {limits.text_chars:,} characters. Paste an excerpt.")
                parts.append(part)
    except ResumeError:
        raise
    except Exception:
        raise ResumeError("The PDF is unreadable. Try saving a new PDF or use LaTeX or pasted text.") from None
    if not parts:
        raise ResumeError("No readable PDF text was found. It may be scanned. Use LaTeX or paste the text.")
    return reviewed_text("\n".join(parts), limits)
