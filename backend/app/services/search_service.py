"""In-memory semantic-ish search over the curated JSON knowledge.

Replaces the old ChromaDB index. The data set is small, so a TF-IDF index
built in pure Python at startup is fast, needs no extra dependencies, uses
almost no memory, and never writes to disk.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.services import knowledge

_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "it",
    "of", "on", "or", "the", "to", "use", "using", "with", "your", "you", "this", "that", "will",
}


def _tokens(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9+#.]+", text.lower()) if w not in _STOP and len(w) > 1]
    words = [w.strip(".") for w in words if w.strip(".")]
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


@dataclass
class Document:
    kind: str
    id: str
    text: str
    record: dict[str, Any]


def _document_text(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in row.items():
        if key in {"id", "source_url", "updated_at", "status", "employment_type"}:
            continue
        if isinstance(value, list):
            parts.append(" ".join(map(str, value)))
        elif isinstance(value, (str, int, float)):
            parts.append(str(value))
    return " ".join(parts)


class TfidfIndex:
    def __init__(self, documents: list[Document]):
        self.documents = documents
        counts = [Counter(_tokens(doc.text)) for doc in documents]
        df: Counter[str] = Counter()
        for c in counts:
            df.update(c.keys())
        n = max(len(documents), 1)
        self.idf = {term: math.log((1 + n) / (1 + freq)) + 1 for term, freq in df.items()}
        self.default_idf = math.log(1 + n) + 1  # terms never seen in the curated data are rare by definition
        self.vectors = [self._weigh(c) for c in counts]

    def _weigh(self, counts: Counter[str]) -> dict[str, float]:
        vec = {t: (1 + math.log(c)) * self.idf.get(t, self.default_idf) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, kinds: tuple[str, ...] | None = None, limit: int = 5) -> list[tuple[Document, float]]:
        q = self._weigh(Counter(_tokens(query)))
        scored = []
        for doc, vec in zip(self.documents, self.vectors):
            if kinds and doc.kind not in kinds:
                continue
            score = sum(weight * vec.get(term, 0.0) for term, weight in q.items())
            scored.append((doc, max(0.0, min(1.0, score))))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]


@lru_cache(maxsize=1)
def index() -> TfidfIndex:
    sources = {
        "jobs": knowledge.jobs(),
        "skills": knowledge.skills(),
        "careers": knowledge.careers(),
        "interviews": knowledge.interviews(),
        "learning": knowledge.learning(),
    }
    docs = [
        Document(kind, str(row.get("id", f"{kind}-{i}")), _document_text(row), row)
        for kind, rows in sources.items()
        for i, row in enumerate(rows)
    ]
    return TfidfIndex(docs)


def similarity(query: str, text: str) -> float:
    """Cosine similarity (0..1) between two free texts, using the curated corpus IDF."""
    idx = index()
    a = idx._weigh(Counter(_tokens(query)))
    b = idx._weigh(Counter(_tokens(text)))
    return max(0.0, min(1.0, sum(w * b.get(t, 0.0) for t, w in a.items())))


def job_text(job: dict[str, Any]) -> str:
    return " ".join([job.get("title", ""), job.get("field", ""), job.get("description", ""),
                     *job.get("required_skills", []), *job.get("preferred_skills", [])])


def retrieve_context(query: str, kinds: tuple[str, ...], limit: int = 3) -> list[str]:
    """Short text snippets from the curated data to ground AI prompts."""
    return [doc.text[:600] for doc, score in index().search(query, kinds, limit) if score > 0]


def status() -> dict[str, Any]:
    idx = index()
    return {"backend": "in-memory TF-IDF", "documents": len(idx.documents)}
