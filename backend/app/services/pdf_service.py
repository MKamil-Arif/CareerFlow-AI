"""Text extraction from uploaded PDF resumes (kept in memory, never saved)."""
from __future__ import annotations

import io

MAX_PAGES = 10


class PdfError(ValueError):
    """The upload is not a readable PDF."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader  # small, pure-Python PDF library

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted and not reader.decrypt(""):
            raise PdfError("The PDF is password-protected.")
        parts = [(page.extract_text() or "") for page in reader.pages[:MAX_PAGES]]
    except PdfError:
        raise
    except Exception as exc:
        raise PdfError(f"Failed to parse PDF: {type(exc).__name__}") from exc
    return "\n".join(parts).strip()
