"""Text extraction from uploaded PDF resumes (kept in memory, never saved)."""
from __future__ import annotations

MAX_PAGES = 10


class PdfError(ValueError):
    """The upload is not a readable PDF."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pymupdf  # imported lazily so the rest of the app works without it in tests

    try:
        with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
            if doc.needs_pass:
                raise PdfError("The PDF is password-protected.")
            parts = [page.get_text() for page in doc.pages(0, min(doc.page_count, MAX_PAGES))]
    except PdfError:
        raise
    except Exception as exc:
        raise PdfError(f"Failed to parse PDF: {type(exc).__name__}") from exc
    return "\n".join(parts).strip()
