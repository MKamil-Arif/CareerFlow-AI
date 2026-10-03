"""Offline logic: resume parsing, learning plans, interview questions and scoring.

These run whenever no AI provider is configured or a provider fails, so every
feature keeps working (with simpler output) on a fresh deployment.
"""
from __future__ import annotations

import re
from typing import Any

from app.services import knowledge, search_service
from app.services.skills import find_in_text

# ---------------------------------------------------------------- resume parsing
SECTION_HEADINGS = {
    "experience": ["experience", "work experience", "professional experience", "employment", "work history", "internships", "internship"],
    "education": ["education", "academic background", "academics", "qualifications", "academic qualifications"],
    "projects": ["projects", "personal projects", "academic projects", "key projects"],
    "certifications": ["certifications", "certificates", "licenses", "courses", "certifications & courses"],
    "skills": ["skills", "technical skills", "core skills", "tools", "technologies", "skills & tools"],
    "other": ["summary", "profile", "objective", "about me", "contact", "languages", "interests", "hobbies",
              "references", "achievements", "awards", "activities", "volunteering"],
}
_HEADING_LOOKUP = {h: section for section, hs in SECTION_HEADINGS.items() for h in hs}
DEGREE_WORDS = re.compile(r"\b(bachelor|master|b\.?s\.?c?|m\.?s\.?c?|b\.?e|m\.?phil|ph\.?d|bba|mba|bscs|bsse|"
                          r"intermediate|f\.?sc|matric|o[- ]levels?|a[- ]levels?|diploma|university|college)\b", re.I)
KNOWN_CITIES = ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad", "Multan", "Peshawar", "Quetta",
                "Sialkot", "Gujranwala", "Hyderabad", "Dubai", "London", "Remote"]


def _heading(line: str) -> str | None:
    clean = re.sub(r"[^a-z& ]", "", line.lower()).strip()
    if 2 < len(clean) <= 40 and len(line.split()) <= 5:
        return _HEADING_LOOKUP.get(clean)
    return None


def _clean_line(line: str) -> str:
    return re.sub(r"^[\s•●▪◦\-–*·]+", "", line).strip()


def parse_resume_offline(text: str) -> dict[str, Any]:
    """Conservative rule-based extraction. Only keeps what is written in the resume."""
    lines = [_clean_line(l) for l in text.splitlines()]
    lines = [l for l in lines if l]
    sections: dict[str, list[str]] = {k: [] for k in SECTION_HEADINGS}
    current = None
    for line in lines:
        heading = _heading(line)
        if heading:
            current = heading
            continue
        if current and len(line) > 2:
            sections[current].append(line[:300])

    name = ""
    for line in lines[:5]:
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z.'-]+", w) for w in words) and not _heading(line):
            name = line.title() if line.isupper() else line
            break

    education = sections["education"] or [l for l in lines if DEGREE_WORDS.search(l)]
    location = ""
    for city in KNOWN_CITIES:
        if city != "Remote" and re.search(rf"\b{city}\b", text):
            location = city + (", Pakistan" if re.search(r"\bPakistan\b", text) else "")
            break

    lowered = text.lower()
    years = [int(y) for y in re.findall(r"(\d{1,2})\+?\s*(?:years|yrs)", lowered)]
    if "senior" in lowered or (years and max(years) >= 6):
        level = "Senior"
    elif years and max(years) >= 2:
        level = "Mid"
    else:
        level = "Entry"

    return {
        "name": name[:120],
        "skills": find_in_text(text)[:100],
        "experience": sections["experience"][:15],
        "education": education[:8],
        "projects": sections["projects"][:15],
        "certifications": sections["certifications"][:15],
        "location": location,
        "career_level": level,
    }


# ---------------------------------------------------------------- learning plan
def plan_targets(gaps: dict[str, Any]) -> list[str]:
    return gaps.get("missing") or gaps.get("improve") or ["Portfolio project"]


def build_plan(job: dict[str, Any], targets: list[str], ai_tasks: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Seven tasks. AI text is used when available; resources always come from curated data."""
    plan = []
    for i in range(7):
        ai = ai_tasks[i] if ai_tasks and i < len(ai_tasks) else {}
        skill = targets[i % len(targets)]
        # Prefer the skill the AI chose only when it is one of our targets.
        if ai.get("skill") and any(ai["skill"].lower() == t.lower() for t in targets):
            skill = next(t for t in targets if t.lower() == ai["skill"].lower())
        rounds = i // len(targets)
        default_title = (f"Learn the basics of {skill}" if rounds == 0 else
                         f"Build a small {job['title']} task using {skill}" if rounds == 1 else
                         f"Review and polish your {skill} work")
        resource = knowledge.resource_or_search(skill)
        plan.append({
            "day": f"Day {i + 1}",
            "skill": skill,
            "title": ai.get("title") or default_title,
            "desc": ai.get("desc") or f"Study {skill} using the linked resource, then apply it to a small exercise relevant to {job['title']}.",
            "completion_criteria": ai.get("completion_criteria") or f"You can explain {skill} in your own words and have one working example saved.",
            "resource_title": resource.get("title", ""),
            "resource_url": resource.get("url", ""),
            "completed": False,
        })
    return plan


# ---------------------------------------------------------------- interview
QUESTION_TYPES = ("technical", "behavioral", "scenario")

OFFLINE_QUESTIONS = {
    "easy": {
        "technical": [
            "What is {skill}, in simple words?",
            "Why is {skill} useful for a {title}?",
            "Name one task where you would use {skill}.",
        ],
        "behavioral": [
            "Tell me a little about yourself.",
            "Why do you want to work as a {title}?",
            "What is one strength you bring to a team?",
        ],
        "scenario": [
            "Your manager gives you a task you don't understand. What do you do first?",
            "You made a small mistake in your work. How would you handle it?",
            "You have two tasks due today. How do you decide which to do first?",
        ],
    },
    "medium": {
        "technical": [
            "Describe how you have used {skill} in a project or task.",
            "What is a common mistake with {skill}, and how do you avoid it?",
            "How would you check that your {skill} work is correct before sharing it?",
        ],
        "behavioral": [
            "Tell me about a time you learned something new quickly. What did you do?",
            "Describe a time you received feedback. How did you respond?",
            "Tell me about a time you worked in a team to finish something on time.",
        ],
        "scenario": [
            "As a {title}, a task needs {skill}, which you've only used a little. How do you deliver it?",
            "A deadline is two days away and something important is broken. What steps do you take?",
            "A client asks for a change that conflicts with the original plan. How do you handle it?",
        ],
    },
    "hard": {
        "technical": [
            "Explain a complex problem you solved with {skill}. What trade-offs did you weigh, and what would you do differently?",
            "How would you teach {skill} to a new teammate and measure whether they really understood it?",
            "Compare two different ways to approach a {skill} task. When would you choose each?",
        ],
        "behavioral": [
            "Tell me about a time you disagreed with a senior colleague. How did you handle it, and what was the outcome?",
            "Describe your biggest professional failure, what caused it, and what you changed afterwards.",
            "Tell me about a time you had to lead without formal authority. How did you get people on board?",
        ],
        "scenario": [
            "As a {title}, your project is behind schedule, the budget is cut and a key teammate leaves. What is your plan for the next two weeks?",
            "Two stakeholders want opposite things and both are senior. As a {title}, how do you decide and communicate it?",
            "You discover an error in work that has already been delivered to a client. What do you do, step by step?",
        ],
    },
}


def question_type(previous: list[str]) -> str:
    return QUESTION_TYPES[len(previous) % len(QUESTION_TYPES)]


def offline_question(job: dict[str, Any] | None, title: str, previous: list[str], difficulty: str = "medium") -> str:
    qtype = question_type(previous)
    skills = (job or {}).get("required_skills", []) or ["the main tools of the role"]
    templates = OFFLINE_QUESTIONS.get(difficulty, OFFLINE_QUESTIONS["medium"])[qtype]
    for n in range(len(templates) * len(skills)):
        candidate = templates[(len(previous) // 3 + n) % len(templates)].format(
            title=title, skill=skills[(len(previous) + n) % len(skills)])
        if candidate not in previous:
            return candidate
    return templates[0].format(title=title, skill=skills[0])


def interview_context(job_title: str, requirements: str) -> list[str]:
    return search_service.retrieve_context(f"{job_title} {requirements}", ("interviews", "careers"), 3)


def offline_evaluate(question: str, answer: str, job: dict[str, Any] | None, difficulty: str = "medium") -> dict[str, Any]:
    """Transparent heuristic rubric used when no AI provider is available."""
    words = re.findall(r"\w+", answer)
    # Easy questions need shorter answers; hard ones need more depth.
    scale = {"easy": 2.0, "medium": 1.0, "hard": 0.75}.get(difficulty, 1.0)
    count = int(len(words) * scale)
    lower = answer.lower()
    sentences = max(1, len(re.findall(r"[.!?]+", answer)))
    job_skills = [s for s in ((job or {}).get("required_skills", []) + (job or {}).get("preferred_skills", []))]
    skill_hits = [s for s in job_skills if s.lower() in lower]
    has_action = bool(re.search(r"\b(i|we)\s+(built|created|designed|implemented|led|wrote|fixed|tested|used|learned|decided|improved)\b", lower))
    has_result = bool(re.search(r"\b(result|outcome|so that|which led|reduced|increased|improved|delivered|achieved|\d+%)", lower))
    has_context = bool(re.search(r"\b(when|while|during|project|situation|team|task)\b", lower))

    if count < 15:
        base = 1
    elif count < 40:
        base = 3
    elif count < 80:
        base = 5
    else:
        base = 6
    correctness = min(10, base + min(3, len(skill_hits)) + (1 if has_action else 0))
    completeness = min(10, base + has_context * 1 + has_action * 1 + has_result * 2)
    avg_sentence = len(words) / sentences
    clarity = min(10, max(1, base + (2 if 8 <= avg_sentence <= 28 else 0) + (1 if count <= 350 else -1)))

    target = {"easy": "30–80", "medium": "80–200", "hard": "150–300"}.get(difficulty, "80–200")
    tips = []
    if count < 40:
        tips.append(f"Give a fuller answer — aim for {target} words.")
    if difficulty != "easy":
        if not has_context:
            tips.append("Start with the situation or context.")
        if not has_action:
            tips.append("Say clearly what you did (\"I built…\", \"I organised…\").")
        if not has_result:
            tips.append("Finish with a concrete result.")
    else:
        completeness = min(10, completeness + 2)
    if job_skills and not skill_hits:
        tips.append("Connect your answer to the role's skills, e.g. " + ", ".join(job_skills[:3]) + ".")
    tips = tips[:3]
    if not tips:
        tips.append("Good answer. Keep it this clear and back up claims with examples.")

    return {
        "correctness": correctness,
        "completeness": completeness,
        "clarity": clarity,
        "feedback": "Offline rubric: " + " ".join(tips),
        "improved_answer": ("Answer directly in 2–4 sentences, then add one short example." if difficulty == "easy" else
                            "Structure it as: situation → your task → what you did and why → the result."),
    }


# ---------------------------------------------------------------- resume suggestions
def offline_resume_suggestions(profile: dict[str, Any], job: dict[str, Any], gaps: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    if gaps.get("have"):
        out.append({"area": "Skills", "suggestion": f"List {', '.join(gaps['have'][:5])} near the top of your skills section, since {job['title']} roles ask for them.",
                    "reason": "Puts your strongest matching evidence where recruiters look first."})
    if gaps.get("missing"):
        out.append({"area": "Skills", "suggestion": f"Do not claim {', '.join(gaps['missing'][:3])} yet. Once you have practised them, add a small project that shows each one.",
                    "reason": "These are required skills your resume does not demonstrate."})
    if profile.get("projects"):
        out.append({"area": "Projects", "suggestion": "For each project, add one line on what you personally built, the tools used, and a result you can verify (link, demo, or measurable outcome).",
                    "reason": "Concrete evidence of skills is more convincing than a list of tools."})
    else:
        out.append({"area": "Projects", "suggestion": f"Add a Projects section with 1–2 projects relevant to {job['title']}, with a link to the code or demo.",
                    "reason": "Entry-level roles often accept projects as evidence of experience."})
    out.append({"area": "Formatting", "suggestion": "Keep it to one page, use consistent dates, and export as a text-based PDF (not a scanned image).",
                "reason": "Makes it readable for people and applicant-tracking systems."})
    return out


# ---------------------------------------------------------------- role recommendations (offline)
def _field_cap(rows: list[dict[str, Any]], count: int, per_field: int = 2) -> list[dict[str, Any]]:
    picked, overflow, per = [], [], {}
    for row in rows:
        key = (row.get("field") or "").split("&")[0].strip().lower()
        if per.get(key, 0) < per_field:
            per[key] = per.get(key, 0) + 1
            picked.append(row)
        else:
            overflow.append(row)
        if len(picked) == count:
            break
    return (picked + overflow)[:count]


def offline_recommend(profile: dict[str, Any], preference: str, exclude: list[str], count: int = 6) -> tuple[list[dict[str, Any]], str]:
    """Best-fitting curated roles across all fields, skipping ones already shown."""
    from app.services import matching_service

    excluded = {t.strip().lower() for t in exclude}
    pool = [j for j in knowledge.jobs() if j["title"].lower() not in excluded]
    note = ""
    if len(pool) < 3:
        pool, note = list(knowledge.jobs()), "You've seen every role in the offline catalog, so the list started over."
    scored = matching_service.match_jobs(profile, pool, top_n=len(pool))
    if preference.strip():
        # Roles that match the stated preference come first; the rest keep their CV ranking.
        def wanted(row):
            return search_service.similarity(preference, search_service.job_text(row) + " " + row.get("location", "")) >= 0.08
        scored = [r for r in scored if wanted(r)] + [r for r in scored if not wanted(r)]
    return _field_cap(scored, count), note


GENERIC_SKILLS = ["Communication", "MS Office", "Problem Solving", "Teamwork", "Time Management"]


def offline_custom_role(profile: dict[str, Any], title: str) -> tuple[dict[str, Any], str]:
    """Closest curated role renamed to the user's title, or a generic starting point."""
    import hashlib

    best, best_score = None, 0.0
    for job in knowledge.jobs():
        score = search_service.similarity(title, job["title"] + " " + job.get("field", "")) * 2 + \
            search_service.similarity(title, search_service.job_text(job))
        if score > best_score:
            best, best_score = job, score
    role = {
        "id": "custom-" + hashlib.sha1(title.lower().encode()).hexdigest()[:10],
        "title": title.strip()[:120],
        "company": "",
        "location": profile.get("location", ""),
        "source": "custom",
        "status": "Your chosen target role",
        "why": "You added this role yourself.",
    }
    if best is not None and best_score >= 0.25:
        role.update({k: best.get(k, "") for k in ("field", "description", "required_skills", "preferred_skills",
                                                  "education_requirements", "experience_requirements")})
        return role, f"AI was unavailable, so requirements were copied from the closest known role ({best['title']}). Check they fit."
    role.update({"field": "", "description": f"Your target role: {title}.", "required_skills": GENERIC_SKILLS,
                 "preferred_skills": [], "education_requirements": "", "experience_requirements": ""})
    return role, "AI was unavailable and this role isn't in the offline catalog, so only general workplace skills are listed."


# ---------------------------------------------------------------- career coach (offline)
def coach_suggestions(job: dict[str, Any] | None, has_profile: bool) -> list[str]:
    if not has_profile:
        return ["How do I start my career search?", "What makes a good CV?", "How do I prepare for interviews?"]
    title = job["title"] if job else "my target role"
    return [f"What should I learn first for {title}?", f"How do I prepare for a {title} interview?",
            "How can I improve my CV?", "Which roles fit my profile?"]


def offline_coach(message: str, profile: dict[str, Any] | None, job: dict[str, Any] | None, gaps: dict[str, Any] | None) -> str:
    """Short, rule-based answers when no AI provider is available."""
    text = message.lower()
    title = job["title"] if job else None
    skills = (profile or {}).get("skills", [])

    def has(*words):
        return any(re.search(rf"\b{w}", text) for w in words)

    if has("hi", "hello", "salam", "hey") and len(text.split()) <= 4:
        return ("Hi! I'm your CareerFlow Coach. Ask me about roles that fit you, skills to learn, your CV, or interview prep."
                + ("" if profile else " Upload your CV first so I can personalise my advice."))
    if has("interview"):
        lines = ["- Practise on the **Interview** page — start at **Easy**, then move up.",
                 "- Use the STAR shape: situation, task, action, result.",
                 "- Prepare 2–3 real examples from your projects or work."]
        if gaps and gaps.get("have"):
            lines.append(f"- Be ready to explain how you used {', '.join(gaps['have'][:2])}.")
        return (f"For {title} interviews:\n" if title else "") + "\n".join(lines)
    if has("learn", "skill", "gap", "improve myself", "course", "study"):
        if gaps and gaps.get("missing"):
            first = gaps["missing"][:3]
            return (f"For {title}, focus on **{', '.join(first)}** first (required, but not yet in your profile).\n"
                    "- Follow your 7-day plan on the **Learning** page.\n- Build one small project that shows each skill.")
        if gaps and gaps.get("improve"):
            return f"You cover the required skills for {title}. Next, add **{', '.join(gaps['improve'][:2])}** to stand out."
        return "Pick a target role on the **Jobs** page — I'll then tell you exactly which skills to learn first."
    if has("cv", "resume", "résumé"):
        tips = ["- Keep it to one page with clear headings.",
                "- Start each experience line with an action verb and a result.",
                "- Put skills that match your target role near the top."]
        if profile and not profile.get("projects"):
            tips.append("- Add 1–2 projects with links — you have none listed yet.")
        return "Quick CV wins:\n" + "\n".join(tips[:4]) + "\nUse the **CV Builder** to generate a clean version."
    if has("salary", "pay", "earn", "income"):
        return ("Salaries vary a lot by city, company and experience. Check current listings for the same title on local job boards "
                "and ask peers in the field. Building in-demand skills is the surest way to raise your range.")
    if has("role", "job", "career", "switch", "field", "fit"):
        if profile:
            roles, _ = offline_recommend(profile, "", [], 3)
            return ("Based on your profile, look at: " + ", ".join(f"**{r['title']}**" for r in roles) +
                    ". See scores and missing skills on the **Jobs** page, or type your own target role there.")
        return "Upload your CV on the **Resume** page and I'll suggest roles that fit your background."
    if has("motivat", "stress", "reject", "confiden", "anxious", "nervous"):
        return ("Rejections are normal — most people apply to many roles before an offer. Set a small weekly goal "
                "(e.g. 5 tailored applications + 1 new skill), track progress, and celebrate small wins.")
    base = "I can help with roles that fit you, skills to learn, your CV, and interview practice."
    if skills:
        base += f" With skills like {', '.join(skills[:3])}, a good next step is choosing a target role on the **Jobs** page."
    return base + " (AI is offline right now, so my answers are simpler than usual.)"


def offline_cv_summary(profile: dict[str, Any], job: dict[str, Any] | None, headline: str) -> str:
    level = {"Entry": "Motivated", "Mid": "Experienced", "Senior": "Senior"}.get(profile.get("career_level", "Entry"), "Motivated")
    role = headline or "professional"
    skills = profile.get("skills", [])[:4]
    edu = profile.get("education", [])
    parts = [f"{level} {role}" + (f" skilled in {', '.join(skills[:-1])} and {skills[-1]}" if len(skills) > 1 else (f" skilled in {skills[0]}" if skills else "")) + "."]
    if edu:
        parts.append(f"Holds {edu[0].split('—')[0].split(' - ')[0].strip()}.")
    if profile.get("projects") or profile.get("experience"):
        parts.append("Brings hands-on experience from real projects and a strong willingness to learn.")
    if job:
        parts.append(f"Looking to contribute as a {job['title']}.")
    return " ".join(parts)
