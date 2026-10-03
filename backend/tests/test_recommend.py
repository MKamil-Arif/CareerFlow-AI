"""Personalised roles: any field, regenerate without repeats, custom roles, and the
whole flow (gap, plan, interview) following whichever role the user targets."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ai_service

MARKETER = {"name": "Hina", "skills": ["SEO", "Canva", "Content Writing", "Social Media Marketing", "Excel"],
            "experience": ["Marketing Intern — Brandly (2025)"], "education": ["BBA Marketing (2025)"],
            "projects": ["Instagram campaign for a bakery"], "certifications": [], "location": "Lahore, Pakistan", "career_level": "Entry"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_offline_recommendations_follow_the_cv_not_just_it(client):
    body = client.post("/api/jobs/recommend", json={"profile": MARKETER}).json()
    assert body["mode"] == "offline" and len(body["jobs"]) == 6
    assert body["jobs"][0]["title"] == "Digital Marketing Executive"
    assert not all(j["field"] == "Software & IT" for j in body["jobs"])


def test_regenerate_returns_different_roles(client):
    first = client.post("/api/jobs/recommend", json={"profile": MARKETER}).json()["jobs"]
    seen = [j["title"] for j in first]
    second = client.post("/api/jobs/recommend", json={"profile": MARKETER, "exclude": seen}).json()["jobs"]
    assert second and not ({j["title"] for j in second} & set(seen))


def test_preference_steers_suggestions(client):
    jobs = client.post("/api/jobs/recommend", json={"profile": MARKETER, "preference": "teaching"}).json()["jobs"]
    assert jobs[0]["title"] == "School Teacher"


def test_custom_role_drives_gap_plan_and_interview(client):
    role = client.post("/api/jobs/custom", json={"profile": MARKETER, "title": "Brand Manager"}).json()["job"]
    assert role["title"] == "Brand Manager" and role["source"] == "custom" and role["required_skills"]
    gaps = client.post("/api/skills/gap", json={"profile": MARKETER, "job": role}).json()
    assert gaps["target_role"] == "Brand Manager"
    plan = client.post("/api/learning-plan", json={"profile": MARKETER, "job": role}).json()
    assert plan["target_role"] == "Brand Manager" and all(d["resource_url"].startswith("https://") for d in plan["plan"])
    q = client.post("/api/interview/start", json={"profile": MARKETER, "job_title": role["title"], "job": role}).json()
    assert "Brand Manager" in q["question"] or q["type"] == "behavioral"


def test_ai_recommendations_are_validated_scored_and_deduplicated(client, monkeypatch):
    roles = {"roles": [
        {"title": "Nutritionist", "field": "Healthcare", "required_skills": ["Nutrition", "Diet Planning", "Counselling"], "preferred_skills": ["Excel"], "why": "Your degree is in nutrition."},
        {"title": "Nutritionist", "required_skills": ["Nutrition", "Diet Planning"]},          # duplicate
        {"title": "Lab Assistant", "required_skills": ["Lab Safety"]},                          # too few skills
        {"title": "Food Quality Officer", "field": "Food", "required_skills": ["Food Safety", "HACCP", "Documentation"]},
    ]}
    monkeypatch.setattr(ai_service, "complete", lambda *a, **k: json.dumps(roles))
    profile = dict(MARKETER, skills=["Nutrition", "Counselling", "Excel"])
    body = client.post("/api/jobs/recommend", json={"profile": profile}).json()
    assert body["mode"] == "ai"
    titles = [j["title"] for j in body["jobs"]]
    assert sorted(titles) == ["Food Quality Officer", "Nutritionist"]
    nutri = next(j for j in body["jobs"] if j["title"] == "Nutritionist")
    assert nutri["source"] == "ai" and str(nutri["id"]).startswith("ai-") and nutri["match"] > 0
    assert set(nutri["matched"]) == {"Nutrition", "Counselling", "Excel"}
    # the browser sends the generated role back; the server accepts it without storing anything
    gap = client.post("/api/skills/gap", json={"profile": profile, "job": nutri}).json()["gaps"]
    assert gap["missing"] == ["Diet Planning"]


def test_target_is_required(client):
    r = client.post("/api/skills/gap", json={"profile": MARKETER})
    assert r.status_code == 422
