"""Interview difficulty levels, the career-coach chat and the CV summary helper."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ai_service, career_service, knowledge

PROFILE = {"name": "Hina", "skills": ["SEO", "Canva", "Content Writing"], "experience": ["Marketing Intern — Brandly (2025)"],
           "education": ["BBA Marketing — UCP (2025)"], "projects": [], "certifications": [], "location": "Lahore", "career_level": "Entry"}
JOB = {"id": 8, "title": "Digital Marketing Executive", "required_skills": ["SEO", "Google Analytics", "Canva"], "preferred_skills": ["Google Ads"]}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_offline_questions_get_shorter_with_easier_levels():
    job = knowledge.job_by_id(8)
    lengths = {}
    for level in ("easy", "medium", "hard"):
        qs, prev = [], []
        for _ in range(6):
            q = career_service.offline_question(job, job["title"], prev, level)
            prev.append(q); qs.append(len(q.split()))
        lengths[level] = sum(qs) / len(qs)
    assert lengths["easy"] < lengths["medium"] < lengths["hard"]
    assert lengths["easy"] <= 15


def test_difficulty_is_passed_through_and_validated(client):
    r = client.post("/api/interview/start", json={"profile": PROFILE, "job_title": JOB["title"], "job": JOB, "difficulty": "easy"}).json()
    assert r["difficulty"] == "easy" and len(r["question"].split()) <= 15
    bad = client.post("/api/interview/start", json={"profile": PROFILE, "job_title": "x", "difficulty": "extreme"})
    assert bad.status_code == 422


def test_ai_question_that_is_too_long_falls_back(client, monkeypatch):
    monkeypatch.setattr(ai_service, "complete", lambda *a, **k: " ".join(["word"] * 60) + "?")
    r = client.post("/api/interview/start", json={"profile": PROFILE, "job_title": JOB["title"], "job": JOB, "difficulty": "easy"}).json()
    assert r["mode"] == "offline"


def test_easy_answers_are_scored_more_generously():
    answer = "SEO means improving a website so it shows up higher in Google search results for the right keywords."
    easy = career_service.offline_evaluate("q", answer, knowledge.job_by_id(8), "easy")
    hard = career_service.offline_evaluate("q", answer, knowledge.job_by_id(8), "hard")
    assert sum(easy[k] for k in ("correctness", "completeness")) > sum(hard[k] for k in ("correctness", "completeness"))


def test_chat_offline_is_short_and_personal(client):
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "What should I learn first?"}], "profile": PROFILE, "job": JOB}).json()
    assert r["mode"] == "offline" and "Google Analytics" in r["reply"]
    assert len(r["reply"].split()) <= 90 and r["suggestions"]


def test_chat_uses_ai_and_caps_length(client, monkeypatch):
    monkeypatch.setattr(ai_service, "complete", lambda *a, **k: "Coach: " + " ".join(["tip"] * 300))
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "help"}]}).json()
    assert r["mode"] == "ai" and not r["reply"].startswith("Coach:") and len(r["reply"].split()) <= 151


def test_chat_validates_conversation(client):
    assert client.post("/api/chat", json={"messages": []}).status_code == 422
    assert client.post("/api/chat", json={"messages": [{"role": "assistant", "content": "hi"}]}).status_code == 422
    assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "x" * 2000}]}).status_code == 422


def test_cv_summary_offline_uses_only_profile_facts(client):
    r = client.post("/api/cv/summary", json={"profile": PROFILE, "job": JOB}).json()
    assert r["mode"] == "offline"
    assert "SEO" in r["summary"] and "BBA Marketing" in r["summary"] and "Digital Marketing Executive" in r["summary"]
