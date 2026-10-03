"""REST API. Stateless: nothing a user sends is stored on the server.

The browser keeps the user's profile, plan, progress and interview history
(localStorage) and sends what each request needs.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app import __version__
from app.config import settings
from app.core.security import limit_ai, limit_default
from app.schemas import (CustomRolePayload, InterviewEvalPayload, InterviewStartPayload, JobTargetPayload, Profile,
                         ProfilePayload, RecommendPayload)
from app.services import ai_service, career_service, knowledge, matching_service, pdf_service, search_service
from app.services.skills import dedupe, find_in_text

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

AI_NOTICE = "AI provider unavailable — showing offline results. Ask the site owner to check the AI configuration."


def _job_or_404(job_id: int) -> dict:
    job = knowledge.job_by_id(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job


def _target(payload) -> dict:
    """The role a request is about: the full role sent by the browser, or a curated job by id."""
    if getattr(payload, "job", None) is not None:
        return payload.job.model_dump()
    if getattr(payload, "job_id", None):
        return _job_or_404(payload.job_id)
    raise HTTPException(422, "Choose a target role first.")


def _profile_dict(profile: Profile) -> dict:
    data = profile.model_dump()
    data["skills"] = dedupe(data["skills"])
    return data


# ---------------------------------------------------------------- meta
@router.get("/health", dependencies=[Depends(limit_default)])
def health():
    return {
        "status": "ok",
        "version": __version__,
        "storage": "none (stateless; user data stays in the browser)",
        "search": search_service.status(),
        "ai": {
            "configured": settings.ai_configured,
            "groq": bool(settings.groq_api_key),
            "gemini": bool(settings.gemini_api_key),
        },
    }


# ---------------------------------------------------------------- resume
@router.post("/resume/analyze", dependencies=[Depends(limit_ai)])
@router.post("/resume/upload", dependencies=[Depends(limit_ai)], include_in_schema=False)
async def analyze_resume(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    if file.content_type not in {"application/pdf", "application/x-pdf", "application/octet-stream", None} and not filename.endswith(".pdf"):
        raise HTTPException(415, "Upload a PDF resume.")
    raw = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, f"Resume is larger than the {settings.max_upload_mb} MB limit.")
    if not raw.startswith(b"%PDF"):
        raise HTTPException(400, "This file is not a readable PDF document.")
    try:
        text = pdf_service.extract_text_from_pdf(raw)
    except pdf_service.PdfError as exc:
        message = str(exc) if "password" in str(exc) else "The PDF is damaged or could not be read. Please export it again and retry."
        raise HTTPException(400, message)
    finally:
        del raw
    if len(text.strip()) < 20:
        raise HTTPException(422, "No selectable text was found. Scanned image-only PDFs are not supported yet.")

    mode, notice = "ai", ""
    try:
        data = ai_service.analyze_resume(text)
        # Keep any explicitly written catalog skills the AI may have missed.
        data["skills"] = dedupe(data["skills"] + find_in_text(text))
    except Exception as exc:
        log.info("Resume analysis using offline parser (%s)", type(exc).__name__)
        data = career_service.parse_resume_offline(text)
        mode = "offline"
        notice = "AI analysis was unavailable, so a simpler offline parser was used. Please review and edit your profile."
    profile = Profile.model_validate(data)
    return {"profile": _profile_dict(profile), "mode": mode, "notice": notice}


@router.post("/resume/improve", dependencies=[Depends(limit_ai)])
def improve_resume(payload: JobTargetPayload):
    profile = _profile_dict(payload.profile)
    job = _target(payload)
    try:
        suggestions, mode = ai_service.improve_resume(profile, job), "ai"
    except Exception as exc:
        log.info("Resume suggestions using offline rules (%s)", type(exc).__name__)
        suggestions, mode = career_service.offline_resume_suggestions(profile, job, matching_service.skill_gaps(profile, job)), "offline"
    return {
        "suggestions": suggestions,
        "mode": mode,
        "notice": "" if mode == "ai" else AI_NOTICE,
        "grounding": "Check every suggestion against your real experience; never add claims you cannot back up.",
    }


# ---------------------------------------------------------------- jobs
@router.get("/jobs", dependencies=[Depends(limit_default)])
def jobs_list(q: str = Query(default="", max_length=120), location: str = Query(default="", max_length=120)):
    rows = knowledge.jobs()
    if q:
        terms = q.casefold().split()
        rows = [j for j in rows if all(t in " ".join([j.get("title", ""), j.get("company", ""), j.get("description", ""),
                                                        *j.get("required_skills", []), *j.get("preferred_skills", [])]).casefold() for t in terms)]
    if location:
        loc = location.casefold()
        rows = [j for j in rows if loc in j.get("location", "").casefold() or "remote" in j.get("location", "").casefold()]
    return {"jobs": rows, "notice": "Curated sample roles; vacancy status has not been verified."}


@router.get("/jobs/{job_id}", dependencies=[Depends(limit_default)])
def job_get(job_id: int):
    return {"job": _job_or_404(job_id)}


@router.post("/jobs/match", dependencies=[Depends(limit_default)])
def match_jobs(payload: ProfilePayload):
    results = matching_service.match_jobs(_profile_dict(payload.profile), knowledge.jobs(), top_n=100)
    return {
        "jobs": results,
        "weights": matching_service.WEIGHTS,
        "notice": "Scores are weighted guidance, not hiring probabilities. Roles are curated examples, not verified openings.",
    }


@router.post("/jobs/recommend", dependencies=[Depends(limit_ai)])
def recommend_jobs(payload: RecommendPayload):
    """Roles chosen for this CV (any field). Send already-shown titles in `exclude` to get different ones."""
    profile = _profile_dict(payload.profile)
    note = ""
    try:
        roles, mode = ai_service.recommend_roles(profile, payload.preference, payload.exclude, payload.count), "ai"
        ranked = matching_service.match_jobs(profile, roles, top_n=len(roles))
    except Exception as exc:
        log.info("Role recommendations from offline catalog (%s)", type(exc).__name__)
        ranked, note = career_service.offline_recommend(profile, payload.preference, payload.exclude, payload.count)
        mode = "offline"
    notice = note or ("" if mode == "ai" else
                      "AI is unavailable, so these roles come from the built-in catalog (many fields, but limited). If none fit, type the role you want under “Already know the role you want?”.")
    return {
        "jobs": ranked,
        "mode": mode,
        "notice": notice,
        "weights": matching_service.WEIGHTS,
        "disclaimer": "These are role types that fit your CV, not live vacancies. Scores are guidance, not hiring probabilities.",
    }


@router.post("/jobs/custom", dependencies=[Depends(limit_ai)])
def custom_job(payload: CustomRolePayload):
    """Build a target role from a title the user types (e.g. 'Digital Marketing Executive')."""
    profile = _profile_dict(payload.profile)
    try:
        role, mode, notice = ai_service.custom_role(profile, payload.title), "ai", ""
    except Exception as exc:
        log.info("Custom role from offline catalog (%s)", type(exc).__name__)
        (role, notice), mode = career_service.offline_custom_role(profile, payload.title), "offline"
    scored = matching_service.match_jobs(profile, [role], top_n=1)[0]
    return {"job": scored, "mode": mode, "notice": notice}


# ---------------------------------------------------------------- skills & plan
@router.post("/skills/gap", dependencies=[Depends(limit_default)])
def skill_gap(payload: JobTargetPayload):
    job = _target(payload)
    return {"target_role": job["title"], "job_id": job["id"], "gaps": matching_service.skill_gaps(_profile_dict(payload.profile), job)}


@router.post("/learning-plan", dependencies=[Depends(limit_ai)])
def learning_plan(payload: JobTargetPayload):
    profile = _profile_dict(payload.profile)
    job = _target(payload)
    gaps = matching_service.skill_gaps(profile, job)
    targets = career_service.plan_targets(gaps)
    context = search_service.retrieve_context(" ".join([job["title"], *targets]), ("learning", "skills"), 4)
    try:
        ai_tasks, mode = ai_service.learning_plan(profile, job, targets, context), "ai"
    except Exception as exc:
        log.info("Learning plan using offline template (%s)", type(exc).__name__)
        ai_tasks, mode = None, "offline"
    return {
        "plan": career_service.build_plan(job, targets, ai_tasks),
        "job_id": job["id"],
        "target_role": job["title"],
        "mode": mode,
        "notice": "" if mode == "ai" else AI_NOTICE,
    }


# ---------------------------------------------------------------- interview
@router.post("/interview/start", dependencies=[Depends(limit_ai)])
def start_interview(payload: InterviewStartPayload):
    profile = _profile_dict(payload.profile)
    if payload.job is not None:
        job = payload.job.model_dump()
    else:
        job = knowledge.job_by_id(payload.job_id) if payload.job_id else None
    if job is None:
        job = next((j for j in knowledge.jobs() if j["title"].casefold() == payload.job_title.casefold()), None)
    title = job["title"] if job else payload.job_title
    requirements = ", ".join(job.get("required_skills", []) + job.get("preferred_skills", [])) if job else ""
    qtype = career_service.question_type(payload.previous)
    try:
        context = career_service.interview_context(title, requirements)
        question = ai_service.interview_question(profile, title, payload.previous, requirements, qtype, context)
        mode = "ai"
    except Exception as exc:
        log.info("Interview question from offline bank (%s)", type(exc).__name__)
        question, mode = career_service.offline_question(job, title, payload.previous), "offline"
    return {
        "question": question,
        "type": qtype,
        "mode": mode,
        "notice": "Practice coaching only; not an official hiring assessment.",
    }


@router.post("/interview/evaluate", dependencies=[Depends(limit_ai)])
def evaluate(payload: InterviewEvalPayload):
    job = payload.job.model_dump() if payload.job is not None else (knowledge.job_by_id(payload.job_id) if payload.job_id else None)
    try:
        result, mode = ai_service.evaluate_answer(payload.question, payload.answer, payload.job_title), "ai"
    except Exception as exc:
        log.info("Interview evaluation using offline rubric (%s)", type(exc).__name__)
        result, mode = career_service.offline_evaluate(payload.question, payload.answer, job), "offline"
    return {
        **result,
        "rubric": {
            "correctness": "technical accuracy and relevance to the role",
            "completeness": "context, your actions, and the outcome",
            "clarity": "organised and concise",
        },
        "mode": mode,
        "notice": "Practice guidance only; scores are not an official hiring assessment.",
    }
