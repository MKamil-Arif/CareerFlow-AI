import json
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL

def _client():
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    return Groq(api_key=GROQ_API_KEY)

def _clean_json(raw: str) -> str:
    """Strip markdown fences and whitespace from LLM JSON output."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()

def analyze_resume(resume_text: str) -> dict:
    """Use Groq to extract structured profile from resume text."""
    prompt = f"""You are a resume parser. Extract structured data from this resume.

Return ONLY valid JSON (no markdown, no explanation) with this exact schema:
{{
  "skills": ["skill1", "skill2"],
  "experience": ["Job Title — Company (duration)"],
  "education": ["Degree — University (year)"],
  "projects": ["Project Name — short description"],
  "certifications": ["cert name"],
  "location": "city, country",
  "career_level": "Entry | Mid | Senior"
}}

If a field has no data, return an empty array or empty string.

RESUME:
{resume_text[:6000]}
"""
    response = _client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500,
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(_clean_json(raw))
    except Exception:
        return {
            "skills": [], "experience": [], "education": [],
            "projects": [], "certifications": [],
            "location": "", "career_level": "Entry"
        }

def generate_explanation(profile: dict, job: dict, matched: list, missing: list) -> str:
    """Generate a 1-2 sentence explanation of why this job fits."""
    prompt = f"""Write a 1-2 sentence explanation of why this candidate fits this job.
Be specific and honest. Mention matched skills positively and missing skills constructively.

Candidate skills: {', '.join(profile.get('skills', []))}
Job title: {job['title']}
Job requires: {', '.join(job['required_skills'])}
Matched skills: {', '.join(matched)}
Missing skills: {', '.join(missing) if missing else 'None'}

Respond with ONLY the explanation text, nothing else."""
    response = _client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()

def generate_skill_gap(profile: dict, job: dict) -> dict:
    """Return categorized skills: have, improve, missing."""
    user_skills = [s.lower() for s in profile.get("skills", [])]
    required = job["required_skills"]
    preferred = job.get("preferred_skills", [])

    have, improve, missing = [], [], []
    for skill in required:
        if skill.lower() in user_skills:
            have.append(skill)
        else:
            missing.append(skill)
    for skill in preferred:
        if skill.lower() in user_skills:
            improve.append(skill)
        else:
            improve.append(skill)

    return {"have": have, "improve": improve, "missing": missing}

def generate_learning_plan(profile: dict, job: dict, gaps: dict) -> list:
    """Ask Groq to generate a 7-day plan based on missing skills."""
    missing = gaps["missing"]
    if not missing:
        missing = ["Advanced " + s for s in gaps["improve"][:3]]

    prompt = f"""Create a 7-day learning plan for someone targeting a "{job['title']}" role.
They already know: {', '.join(profile.get('skills', []))}
They need to learn: {', '.join(missing)}

Return ONLY a valid JSON array of exactly 7 objects with this schema:
[
  {{"day": "Day 1", "title": "Short title", "desc": "One-sentence actionable task"}},
  ...
]
No markdown, no explanation."""
    response = _client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=900,
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(_clean_json(raw))
    except Exception:
        return [{"day": f"Day {i+1}", "title": "Study " + missing[i % len(missing)],
                 "desc": "Complete a focused learning session."} for i in range(7)]

def generate_interview_question(profile: dict, job_title: str, previous: list = None) -> str:
    """Generate a role-specific interview question."""
    previous = previous or []
    prompt = f"""Generate ONE interview question for a "{job_title}" role.
The candidate knows: {', '.join(profile.get('skills', []))}
{"Do NOT repeat these: " + " | ".join(previous) if previous else ""}

Return ONLY the question text."""
    response = _client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=120,
    )
    return response.choices[0].message.content.strip()

def evaluate_interview_answer(question: str, answer: str, job_title: str) -> dict:
    """Score and give feedback on a candidate's answer."""
    prompt = f"""Evaluate this interview answer for a "{job_title}" role.

Question: {question}
Answer: {answer}

Return ONLY valid JSON with this schema:
{{
  "correctness": 0-10,
  "completeness": 0-10,
  "clarity": 0-10,
  "feedback": "2-3 sentences of specific feedback"
}}
No markdown."""
    response = _client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=400,
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(_clean_json(raw))
    except Exception:
        return {"correctness": 5, "completeness": 5, "clarity": 5,
                "feedback": "Could not evaluate. Please try again."}

def improve_resume(profile: dict, job: dict) -> list:
    """Suggest resume improvements aligned to a target job."""
    prompt = f"""Suggest 4 resume improvements for a candidate targeting "{job['title']}".

Candidate current skills: {', '.join(profile.get('skills', []))}
Candidate projects: {', '.join(profile.get('projects', []))}
Job requires: {', '.join(job['required_skills'])}

Return ONLY a JSON array of 4 objects:
[{{"area": "Skills|Projects|Summary|Formatting", "suggestion": "specific actionable advice"}}]
No markdown."""
    response = _client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=600,
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(_clean_json(raw))
    except Exception:
        return [{"area": "General", "suggestion": "Tailor your resume to the role."}]