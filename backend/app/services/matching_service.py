"""Transparent weighted matching for curated jobs."""
import re
from app.services import rag_service

WEIGHTS = {"required_skills": 40, "profile_similarity": 25, "education": 10, "experience": 10, "location": 10, "preferred_skills": 5}

def _norm(value):
    return re.sub(r"[^a-z0-9+#.]", " ", str(value).lower()).strip()

def compute_structured_score(profile, job):
    """Compatibility API returning the structured portion and skill lists."""
    user = {_norm(s) for s in profile.get("skills", [])}
    required = job.get("required_skills", [])
    preferred = job.get("preferred_skills", [])
    matched_req = [s for s in required if _norm(s) in user]
    missing = [s for s in required if _norm(s) not in user]
    matched_pref = [s for s in preferred if _norm(s) in user]
    score = (len(matched_req) / max(len(required), 1)) * WEIGHTS["required_skills"]
    score += (len(matched_pref) / max(len(preferred), 1)) * WEIGHTS["preferred_skills"]
    return round(score), matched_req + matched_pref, missing

def _semantic_fallback(profile, job):
    profile_text = " ".join(profile.get("skills", []) + profile.get("experience", []) + profile.get("projects", []))
    job_text = " ".join([job.get("title", ""), job.get("description", ""), *job.get("required_skills", [])])
    terms = {_norm(t) for t in profile_text.split() if len(t) > 2}
    target = {_norm(t) for t in job_text.split() if len(t) > 2}
    return len(terms & target) / max(len(target), 1)

def _eligibility(profile, job):
    required_edu = str(job.get("education_requirements", "")).lower()
    education = " ".join(profile.get("education", [])).lower()
    edu = 10 if not required_edu or "not specified" in required_edu else (10 if any(x in education for x in required_edu.split()) else 4 if education else 3)
    wanted_exp = str(job.get("experience_requirements", "")).lower()
    experience = " ".join(profile.get("experience", [])).lower()
    exp = 10 if not wanted_exp or "entry" in wanted_exp or "not specified" in wanted_exp else (10 if experience else 4)
    loc = str(job.get("location", "")).lower()
    userloc = str(profile.get("location", "")).lower()
    location = 10 if userloc and (userloc in loc or "remote" in loc) else (7 if "remote" in loc else 4 if userloc else 5)
    return edu, exp, location

def match_jobs(profile, all_jobs, top_n=5):
    query = " ".join([profile.get("career_level", "Entry"), *profile.get("skills", []), *profile.get("experience", []), *profile.get("projects", [])])
    sem_ids, similarities = rag_service.search_knowledge(query, "jobs", max(top_n * 3, len(all_jobs)))
    sem = {int(i): s for i, s in zip(sem_ids, similarities) if i.isdigit()}
    results = []
    for job in all_jobs:
        base, matched, missing = compute_structured_score(profile, job)
        semantic = sem.get(job["id"], _semantic_fallback(profile, job))
        edu, exp, loc = _eligibility(profile, job)
        req_component = (len(matched) - sum(1 for s in matched if s in job.get("preferred_skills", []))) / max(len(job.get("required_skills", [])), 1) * 40
        pref_component = (sum(1 for s in matched if s in job.get("preferred_skills", [])) / max(len(job.get("preferred_skills", [])), 1)) * 5
        score = round(req_component + max(0, min(1, semantic)) * 25 + edu + exp + loc + pref_component)
        reasons = []
        if matched: reasons.append("your profile includes " + ", ".join(matched[:4]))
        if missing: reasons.append("the profile does not yet demonstrate " + ", ".join(missing[:3]))
        explanation = f"{job.get('title')} at {job.get('company')} matches because " + ("; ".join(reasons) if reasons else "its role description is relevant to your profile").rstrip(".") + ". Scores are weighted guidance, not a hiring probability."
        results.append({"id": job["id"], "title": job["title"], "company": job["company"], "location": job["location"], "description": job.get("description", ""), "required_skills": job.get("required_skills", []), "preferred_skills": job.get("preferred_skills", []), "match": max(0, min(100, score)), "matched": matched, "missing": missing, "explain": explanation, "source_url": job.get("source_url", ""), "updated_at": job.get("updated_at", ""), "status": job.get("status", "Curated sample — availability not verified"), "score_breakdown": {"required_skills": round(req_component), "profile_similarity": round(semantic * 25), "education": edu, "experience": exp, "location": loc, "preferred_skills": round(pref_component)}})
    return sorted(results, key=lambda item: item["match"], reverse=True)[:top_n]
