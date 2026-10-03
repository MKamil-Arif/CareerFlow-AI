"""Skill names: canonical forms, common aliases, and detection in free text.

"ReactJS", "React.js" and "react" all count as the job requirement "React",
so a profile is not penalised for spelling a skill differently.
"""
from __future__ import annotations

import re
from functools import lru_cache

from app.services import knowledge

# alias (lower case) -> canonical display name
ALIASES: dict[str, str] = {
    "js": "JavaScript", "javascript": "JavaScript", "es6": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript",
    "reactjs": "React", "react.js": "React", "react js": "React",
    "nextjs": "Next.js", "next js": "Next.js", "next.js": "Next.js",
    "node": "Node.js", "nodejs": "Node.js", "node js": "Node.js", "node.js": "Node.js",
    "html5": "HTML", "css3": "CSS",
    "rest": "REST APIs", "rest api": "REST APIs", "restful": "REST APIs", "restful apis": "REST APIs",
    "restful api": "REST APIs", "rest apis": "REST APIs",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "ms excel": "Excel", "microsoft excel": "Excel",
    "powerbi": "Power BI", "power bi": "Power BI",
    "py": "Python", "python3": "Python",
    "github": "Git", "git": "Git",
    "fast api": "FastAPI", "fastapi": "FastAPI",
    "pandas": "Pandas", "redux toolkit": "Redux",
}

# Extra skills recognised in resumes even if no curated job asks for them yet.
EXTRA_SKILLS = [
    "Java", "C++", "C#", "Rust", "PHP", "Kotlin", "Swift", "Dart", "Flutter",
    "Django", "Flask", "Express.js", "Vue", "Angular", "Tailwind CSS", "Bootstrap",
    "MySQL", "MongoDB", "Firebase", "AWS", "Azure", "Google Cloud", "Linux",
    "NumPy", "Matplotlib", "Machine Learning", "Tableau", "Figma", "GraphQL", "Kubernetes",
]


def _key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


@lru_cache(maxsize=1)
def catalog() -> tuple[str, ...]:
    """Every skill name the app knows, canonical spelling, longest first."""
    names: set[str] = set(EXTRA_SKILLS) | set(ALIASES.values())
    for job in knowledge.jobs():
        names.update(job.get("required_skills", []) + job.get("preferred_skills", []))
    for row in knowledge.skills():
        if row.get("name"):
            names.add(row["name"])
    for row in knowledge.learning():
        if row.get("skill"):
            names.add(row["skill"])
    return tuple(sorted(names, key=lambda s: (-len(s), s)))


@lru_cache(maxsize=1)
def _canonical_map() -> dict[str, str]:
    mapping = {_key(name): name for name in catalog()}
    mapping.update(ALIASES)
    return mapping


def canonical(skill: str) -> str:
    """Comparison key for a skill: the canonical name in lower case."""
    key = _key(skill)
    return _canonical_map().get(key, key).lower()


def display(skill: str) -> str:
    """Canonical display spelling if known, otherwise the cleaned input."""
    key = _key(skill)
    return _canonical_map().get(key, str(skill).strip())


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not str(value).strip():
            continue
        key = canonical(value)
        if key not in seen:
            seen.add(key)
            out.append(display(value))
    return out


# Skill names that are also everyday English words ("excel at", "express ideas",
# "swift delivery"). These only count when written with their capital letter.
CASE_SENSITIVE = {"Excel", "Swift", "Rust", "Dart", "Flutter", "Express", "Vue", "Angular", "Linux"}


def find_in_text(text: str) -> list[str]:
    """Skills explicitly written in the text, matched as whole words."""
    found: list[str] = []
    for term in sorted(set(catalog()) | set(ALIASES), key=len, reverse=True):
        if len(term) <= 2:
            # Short aliases ("js", "ts", "py") only count in capitals: "JS".
            candidate, flags = term.upper(), 0
        elif term in CASE_SENSITIVE:
            candidate, flags = term, 0
        else:
            candidate, flags = term, re.IGNORECASE
        pattern = r"(?<![\w+#.])" + re.escape(candidate) + r"(?![\w+#]|\.\w)"
        if re.search(pattern, text, flags):
            found.append(display(term))
    return dedupe(found)
