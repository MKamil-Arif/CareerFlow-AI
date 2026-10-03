from app.services import career_service, knowledge

RESUME = """AYESHA KHAN
Lahore, Pakistan | ayesha@example.com

SKILLS
Python, SQL, Git, ReactJS, MS Excel

EXPERIENCE
- Data Intern — Acme Analytics (2025)

EDUCATION
BS Computer Science — University of the Punjab (2025)

PROJECTS
- Sales dashboard — cleaned data with Pandas and built charts
"""


def test_offline_parser_extracts_sections():
    p = career_service.parse_resume_offline(RESUME)
    assert p["name"] == "Ayesha Khan"
    assert p["location"] == "Lahore, Pakistan"
    for skill in ("Python", "SQL", "Git", "React", "Excel", "Pandas"):
        assert skill in p["skills"]
    assert p["experience"] == ["Data Intern — Acme Analytics (2025)"]
    assert p["education"][0].startswith("BS Computer Science")
    assert p["projects"][0].startswith("Sales dashboard")
    assert p["career_level"] == "Entry"


def test_plan_has_seven_days_and_curated_links():
    job = knowledge.job_by_id(1)
    plan = career_service.build_plan(job, ["React", "TypeScript"])
    assert [d["day"] for d in plan] == [f"Day {i}" for i in range(1, 8)]
    assert plan[0]["resource_url"] == "https://react.dev/learn"
    assert plan[1]["resource_url"].startswith("https://www.typescriptlang.org/")
    assert all(d["completed"] is False for d in plan)
    assert len({d["title"] for d in plan}) > 2  # not the same title seven times


def test_offline_questions_rotate_and_do_not_repeat():
    job = knowledge.job_by_id(4)
    previous = []
    for _ in range(6):
        q = career_service.offline_question(job, job["title"], previous)
        assert q not in previous
        previous.append(q)


def test_offline_evaluation_rewards_structure():
    weak = career_service.offline_evaluate("q", "I dunno", None)
    strong = career_service.offline_evaluate(
        "q",
        "During a university project our team needed a REST API. I built the endpoints in Python with FastAPI, "
        "wrote tests for each route and fixed two bugs found in review. As a result the API was delivered a week early "
        "and the frontend team integrated it without changes. I learned to agree on the contract first.",
        knowledge.job_by_id(4),
    )
    for key in ("correctness", "completeness", "clarity"):
        assert 0 <= weak[key] <= 10 and 0 <= strong[key] <= 10
        assert strong[key] > weak[key]
