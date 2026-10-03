from app.services import knowledge
from app.services.matching_service import WEIGHTS, match_jobs, skill_gaps, skill_overlap


def test_required_and_preferred_skills_are_reported():
    profile = {"skills": ["python", "git"], "education": [], "experience": [], "location": ""}
    job = {"required_skills": ["Python", "SQL"], "preferred_skills": ["Git"]}
    o = skill_overlap(profile, job)
    assert o["matched_required"] == ["Python"] and o["matched_preferred"] == ["Git"]
    assert o["missing_required"] == ["SQL"] and o["missing_preferred"] == []


def test_match_score_is_bounded_and_breakdown_adds_up():
    profile = {"skills": ["Python", "Git"], "experience": [], "education": [], "projects": [], "location": "Lahore, Pakistan", "career_level": "Entry"}
    results = match_jobs(profile, knowledge.jobs(), 100)
    assert len(results) == len(knowledge.jobs())
    for r in results:
        assert 0 <= r["match"] <= 100
        assert set(r["score_breakdown"]) == set(WEIGHTS)
        assert sum(r["score_breakdown"].values()) == r["match"]
        for key, value in r["score_breakdown"].items():
            assert 0 <= value <= WEIGHTS[key]
    assert results == sorted(results, key=lambda r: (-r["match"], r["id"]))
    assert results[0]["title"] in {"Junior Python Developer", "Backend Developer (Python)"}


def test_location_matches_city_inside_longer_strings():
    from app.services.matching_service import eligibility
    job = {"location": "Karachi (Hybrid)"}
    assert eligibility({"location": "Karachi, Pakistan"}, job)[2] == 10
    assert eligibility({"location": "Lahore, Pakistan"}, job)[2] == 3
    assert eligibility({"location": ""}, {"location": "Remote"})[2] == 10


def test_skill_gap_columns():
    job = {"title": "Dev", "required_skills": ["Python", "SQL"], "preferred_skills": ["Docker", "Git"]}
    gaps = skill_gaps({"skills": ["python", "git"]}, job)
    assert gaps["have"] == ["Python", "Git"]
    assert gaps["missing"] == ["SQL"]
    assert gaps["improve"] == ["Docker"]  # preferred skills you do NOT have yet
