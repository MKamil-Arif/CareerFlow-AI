import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import pdf_service

PROFILE = {"name": "Test", "skills": ["Python", "Git", "SQL"], "experience": [], "education": ["BS CS"],
           "projects": ["API project"], "certifications": [], "location": "Lahore, Pakistan", "career_level": "Entry"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_reports_stateless(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["ai"]["configured"] is False
    assert body["search"]["documents"] > 0
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "CareerFlow" in r.text
    assert "Content-Security-Policy" in r.headers


def test_match_gap_plan_flow_offline(client):
    jobs = client.post("/api/jobs/recommend", json={"profile": PROFILE}).json()["jobs"]
    assert jobs and all(0 <= j["match"] <= 100 for j in jobs)
    target = next(j["id"] for j in jobs if isinstance(j["id"], int))
    gaps = client.post("/api/skills/gap", json={"profile": PROFILE, "job_id": target}).json()["gaps"]
    assert set(gaps) >= {"have", "missing", "improve"}
    plan = client.post("/api/learning-plan", json={"profile": PROFILE, "job_id": target}).json()
    assert plan["mode"] == "offline" and len(plan["plan"]) == 7
    tips = client.post("/api/resume/improve", json={"profile": PROFILE, "job_id": target}).json()
    assert tips["mode"] == "offline" and tips["suggestions"]


def test_interview_offline(client):
    start = client.post("/api/interview/start", json={"profile": PROFILE, "job_title": "Junior Python Developer", "job_id": 6, "previous": []}).json()
    assert start["mode"] == "offline" and start["question"]
    ev = client.post("/api/interview/evaluate", json={"question": start["question"], "answer": "I built an API in Python.", "job_title": "Junior Python Developer", "job_id": 6}).json()
    assert ev["mode"] == "offline" and 0 <= ev["clarity"] <= 10


def test_resume_upload_validation(client, monkeypatch):
    r = client.post("/api/resume/analyze", files={"file": ("cv.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400
    monkeypatch.setattr(pdf_service, "extract_text_from_pdf", lambda raw: "JANE DOE\nKarachi\nSKILLS\nPython, SQL, Docker\n")
    r = client.post("/api/resume/analyze", files={"file": ("cv.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "offline" and body["notice"]
    assert {"Python", "SQL", "Docker"} <= set(body["profile"]["skills"])


def test_validation_errors_are_readable(client):
    r = client.post("/api/skills/gap", json={"profile": PROFILE, "job_id": 0})
    assert r.status_code == 422 and r.json()["detail"].startswith("Invalid input")


def test_rate_limit(client):
    from app.core import security
    limiter = security.RateLimiter(2)
    limiter.check("x"); limiter.check("x")
    with pytest.raises(Exception) as err:
        limiter.check("x")
    assert getattr(err.value, "status_code", None) == 429


def test_ai_mode_is_used_when_provider_answers(client, monkeypatch):
    from app.services import ai_service

    def fake(prompt, **kwargs):
        if "7 daily learning tasks" in prompt:
            return '{"tasks": [' + ",".join('{"skill": "SQL", "title": "Day task %d", "desc": "d", "completion_criteria": "c"}' % i for i in range(7)) + "]}"
        if "interview practice question" in prompt:
            return "How would you design a REST endpoint for orders?"
        return '{"correctness": 8, "completeness": 7, "clarity": 9, "feedback": "Good", "improved_answer": "x"}'

    monkeypatch.setattr(ai_service, "complete", fake)
    plan = client.post("/api/learning-plan", json={"profile": PROFILE, "job_id": 4}).json()
    assert plan["mode"] == "ai" and plan["plan"][0]["title"] == "Day task 0"
    assert plan["plan"][0]["resource_url"]  # links always come from curated data, never the AI
    q = client.post("/api/interview/start", json={"profile": PROFILE, "job_title": "x", "job_id": 4}).json()
    assert q["mode"] == "ai" and q["question"].startswith("How would")
    ev = client.post("/api/interview/evaluate", json={"question": "q", "answer": "a", "job_title": "x"}).json()
    assert ev["mode"] == "ai" and ev["clarity"] == 9


def test_removed_endpoints_are_gone(client):
    assert client.post("/api/jobs/match", json={"profile": PROFILE}).status_code in (404, 405)
    assert client.post("/api/resume/upload").status_code in (404, 405)


def test_real_pdf_is_parsed_end_to_end(client):
    from pathlib import Path
    pdf = (Path(__file__).parent / "fixtures" / "sample_resume.pdf").read_bytes()
    body = client.post("/api/resume/analyze", files={"file": ("cv.pdf", pdf, "application/pdf")}).json()
    p = body["profile"]
    assert p["name"] == "Sara Ahmed" and p["location"].startswith("Lahore")
    assert {"JavaScript", "React", "HTML", "CSS", "Git"} <= set(p["skills"])
    assert p["education"] and p["experience"] and p["projects"]
