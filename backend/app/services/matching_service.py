"""Transparent, weighted 0-100 matching between a profile and curated jobs."""
from __future__ import annotations

import re
from typing import Any

from app.services import search_service
from app.services.skills import canonical

WEIGHTS = {
    "required_skills": 40,
    "profile_similarity": 25,
    "education": 10,
    "experience": 10,
    "location": 10,
    "preferred_skills": 5,
}


def skill_overlap(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, list[str]]:
    """Which required/preferred job skills the profile does and doesn't show."""
    have = {canonical(s) for s in profile.get("skills", [])}
    required = job.get("required_skills", [])
    preferred = job.get("preferred_skills", [])
    return {
        "matched_required": [s for s in required if canonical(s) in have],
        "missing_required": [s for s in required if canonical(s) not in have],
        "matched_preferred": [s for s in preferred if canonical(s) in have],
        "missing_preferred": [s for s in preferred if canonical(s) not in have],
    }


def compute_structured_score(profile: dict[str, Any], job: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    """Skills-only portion of the score (max 45) plus matched and missing skills."""
    o = skill_overlap(profile, job)
    score = len(o["matched_required"]) / max(len(job.get("required_skills", [])), 1) * WEIGHTS["required_skills"]
    score += len(o["matched_preferred"]) / max(len(job.get("preferred_skills", [])), 1) * WEIGHTS["preferred_skills"]
    return round(score), o["matched_required"] + o["matched_preferred"], o["missing_required"]


def _cities(value: str) -> set[str]:
    words = re.findall(r"[a-z]+", value.lower())
    return {w for w in words if w not in {"remote", "hybrid", "onsite", "on", "site", "pakistan"} and len(w) > 2}


def eligibility(profile: dict[str, Any], job: dict[str, Any]) -> tuple[int, int, int]:
    """Education, experience and location points (each out of 10)."""
    has_education = bool(profile.get("education"))
    has_experience = bool(profile.get("experience"))
    has_projects = bool(profile.get("projects"))

    edu_req = str(job.get("education_requirements", "")).lower()
    if not edu_req or "not specified" in edu_req or has_education:
        edu = 10
    elif "equivalent" in edu_req and (has_experience or has_projects):
        edu = 7
    else:
        edu = 3

    exp_req = str(job.get("experience_requirements", "")).lower()
    if not exp_req or "not specified" in exp_req or has_experience:
        exp = 10
    elif "entry" in exp_req:
        exp = 10 if has_projects else 8
    elif "project" in exp_req and has_projects:
        exp = 8
    else:
        exp = 4

    job_loc = str(job.get("location", ""))
    user_loc = str(profile.get("location", ""))
    if not job_loc.strip() or "flexible" in job_loc.lower() or "any" == job_loc.lower().strip():
        loc = 8
    elif "remote" in job_loc.lower():
        loc = 10
    elif user_loc and _cities(user_loc) & _cities(job_loc):
        loc = 10
    elif not user_loc:
        loc = 5
    else:
        loc = 3
    return edu, exp, loc


def profile_query(profile: dict[str, Any]) -> str:
    return " ".join([
        profile.get("career_level", ""),
        *profile.get("skills", []),
        *profile.get("experience", []),
        *profile.get("projects", []),
        *profile.get("certifications", []),
    ])


def match_jobs(profile: dict[str, Any], all_jobs: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    query = profile_query(profile)
    results = []
    for job in all_jobs:
        o = skill_overlap(profile, job)
        required = job.get("required_skills", [])
        preferred = job.get("preferred_skills", [])
        req_points = len(o["matched_required"]) / max(len(required), 1) * WEIGHTS["required_skills"]
        pref_points = len(o["matched_preferred"]) / max(len(preferred), 1) * WEIGHTS["preferred_skills"] if preferred else WEIGHTS["preferred_skills"]
        # TF-IDF cosine values for short texts are naturally low; 0.5+ is a strong match.
        similarity = min(1.0, search_service.similarity(query, search_service.job_text(job)) * 2)
        sim_points = similarity * WEIGHTS["profile_similarity"]
        edu, exp, loc = eligibility(profile, job)
        breakdown = {
            "required_skills": round(req_points),
            "profile_similarity": round(sim_points),
            "education": edu,
            "experience": exp,
            "location": loc,
            "preferred_skills": round(pref_points),
        }
        score = max(0, min(100, sum(breakdown.values())))
        matched = o["matched_required"] + o["matched_preferred"]
        reasons = []
        if matched:
            reasons.append("your profile shows " + ", ".join(matched[:4]))
        if o["missing_required"]:
            reasons.append("it does not yet demonstrate " + ", ".join(o["missing_required"][:3]))
        where = f" at {job['company']}" if job.get("company") and job.get("company") != "Sample employer" else ""
        explanation = (
            f"{job.get('title')}{where}: "
            + ("; ".join(reasons) if reasons else "the role description is related to your profile")
            + ". Scores are weighted guidance, not a hiring probability."
        )
        results.append({
            "id": job["id"],
            "title": job["title"],
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "description": job.get("description", ""),
            "required_skills": required,
            "preferred_skills": preferred,
            "match": score,
            "matched": matched,
            "missing": o["missing_required"],
            "missing_preferred": o["missing_preferred"],
            "explain": explanation,
            "source_url": job.get("source_url", ""),
            "updated_at": job.get("updated_at", ""),
            "status": job.get("status", "Curated sample — availability not verified"),
            "field": job.get("field", ""),
            "source": job.get("source", "catalog"),
            "why": job.get("why", ""),
            "education_requirements": job.get("education_requirements", ""),
            "experience_requirements": job.get("experience_requirements", ""),
            "score_breakdown": breakdown,
        })
    results.sort(key=lambda item: (-item["match"], item["id"]))
    return results[:top_n]


def skill_gaps(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """have = job skills already shown; missing = required gaps; improve = preferred gaps."""
    o = skill_overlap(profile, job)
    return {
        "have": o["matched_required"] + o["matched_preferred"],
        "missing": o["missing_required"],
        "improve": o["missing_preferred"],
        "labels": {
            "have": "Required or preferred skills your profile already shows",
            "missing": "Required skills not demonstrated in your profile — learn these first",
            "improve": "Preferred (nice-to-have) skills that would strengthen your application",
        },
        "reasons": {s: f"{s} is a required skill for {job['title']}." for s in o["missing_required"]},
    }
