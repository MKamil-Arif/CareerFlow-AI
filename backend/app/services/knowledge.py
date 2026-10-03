"""Read-only curated data, loaded from JSON once at import time.

There is no database: every record the app serves comes from the files in
`app/data/`, and every user-specific record lives in the user's browser.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from app.config import DATA_DIR

log = logging.getLogger(__name__)


def _load(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / f"{name}.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.exception("Could not load %s", path)
        return []
    return [row for row in rows if isinstance(row, dict)]


@lru_cache(maxsize=None)
def jobs() -> list[dict[str, Any]]:
    return _load("jobs")


@lru_cache(maxsize=None)
def skills() -> list[dict[str, Any]]:
    return _load("skills")


@lru_cache(maxsize=None)
def careers() -> list[dict[str, Any]]:
    return _load("careers")


@lru_cache(maxsize=None)
def interviews() -> list[dict[str, Any]]:
    return _load("interviews")


@lru_cache(maxsize=None)
def learning() -> list[dict[str, Any]]:
    return _load("learning")


def job_by_id(job_id: int) -> dict[str, Any] | None:
    return next((job for job in jobs() if job.get("id") == job_id), None)


def resource_for(skill: str) -> dict[str, str] | None:
    """Official learning resource for a skill, if one is curated."""
    from app.services.skills import canonical

    key = canonical(skill)
    for row in learning():
        if canonical(row.get("skill", "")) == key:
            return {"title": row.get("title", ""), "url": row.get("source_url", ""), "source": row.get("source", "")}
    return None


def resource_or_search(skill: str) -> dict[str, str]:
    """Curated resource if we have one, otherwise a free tutorial search for any field."""
    from urllib.parse import quote_plus

    found = resource_for(skill)
    if found:
        return found
    return {
        "title": f"Find free tutorials: {skill}",
        "url": "https://www.youtube.com/results?search_query=" + quote_plus(f"{skill} tutorial for beginners"),
        "source": "YouTube search",
    }
