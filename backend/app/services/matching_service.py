from app.services import rag_service, ai_service

def compute_structured_score(profile: dict, job: dict) -> tuple:
    """Return (score_0_100, matched_skills, missing_skills)."""
    user_skills = {s.lower() for s in profile.get("skills", [])}
    required = job["required_skills"]
    preferred = job.get("preferred_skills", [])

    if not required:
        return 0, [], []

    matched_req = [s for s in required if s.lower() in user_skills]
    missing_req = [s for s in required if s.lower() not in user_skills]
    matched_pref = [s for s in preferred if s.lower() in user_skills]

    # Weights from PRD Section 13
    skill_score = (len(matched_req) / len(required)) * 40
    pref_score = (len(matched_pref) / max(len(preferred), 1)) * 5
    edu_score = 10 if profile.get("education") else 5
    exp_score = 10 if profile.get("experience") else 4
    loc_score = 10 if profile.get("location") and profile["location"].lower() in job["location"].lower() else 6

    total = skill_score + pref_score + edu_score + exp_score + loc_score
    return round(total), matched_req + matched_pref, missing_req

def match_jobs(profile: dict, all_jobs: list, top_n: int = 5) -> list:
    """Hybrid matching: semantic + structured + LLM explanation."""
    # Build a query string from the profile
    query = f"{profile.get('career_level','Entry')} developer with skills: {', '.join(profile.get('skills', []))}"

    # Semantic retrieval from ChromaDB
    semantic_ids = rag_service.search_jobs(query, n_results=top_n * 2)
    candidate_jobs = [j for j in all_jobs if j["id"] in semantic_ids] or all_jobs[:top_n * 2]

    results = []
    for job in candidate_jobs:
        score, matched, missing = compute_structured_score(profile, job)
        results.append({
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "match": score,
            "matched": matched,
            "missing": missing,
            "explain": ""  # filled lazily to save API calls
        })

    results.sort(key=lambda x: x["match"], reverse=True)
    top = results[:top_n]

    # Generate explanation only for top 3 (to save tokens/time)
    for r in top[:3]:
        try:
            job = next(j for j in all_jobs if j["id"] == r["id"])
            r["explain"] = ai_service.generate_explanation(profile, job, r["matched"], r["missing"])
        except Exception:
            r["explain"] = "Recommended based on your skills and target role."
    return top