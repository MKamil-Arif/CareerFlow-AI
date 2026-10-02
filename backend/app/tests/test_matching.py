from app.services.matching_service import compute_structured_score, match_jobs

def test_required_and_preferred_skills_are_reported():
    profile = {"skills": ["python", "git"], "education": [], "experience": [], "location": ""}
    job = {"required_skills": ["Python", "SQL"], "preferred_skills": ["Git"]}
    score, matched, missing = compute_structured_score(profile, job)
    assert score == 25
    assert matched == ["Python", "Git"]
    assert missing == ["SQL"]

def test_match_score_is_bounded_and_transparent(monkeypatch):
    monkeypatch.setattr("app.services.rag_service.search_knowledge", lambda *args, **kwargs: ([], []))
    profile = {"skills": ["Python", "Git"], "experience": [], "education": [], "location": "Remote", "career_level": "Entry"}
    jobs = [{"id": 1, "title": "Python Developer", "company": "Example", "location": "Remote", "required_skills": ["Python", "SQL"], "preferred_skills": ["Git"], "description": "Build Python APIs"}]
    result = match_jobs(profile, jobs, 5)[0]
    assert 0 <= result["match"] <= 100
    assert set(result["score_breakdown"]) == {"required_skills", "profile_similarity", "education", "experience", "location", "preferred_skills"}
    assert "not yet demonstrate" in result["explain"]
