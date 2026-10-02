from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.schemas import (
    Profile, ProfilePayload, JobTargetPayload,
    InterviewStartPayload, InterviewEvalPayload
)
from app.services import pdf_service, ai_service, rag_service, matching_service

app = FastAPI(title="CareerFlow AI", version="1.0.0")

# CORS — allow frontend on any origin (tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load jobs into ChromaDB at startup
JOBS_PATH = Path(__file__).parent / "data" / "jobs.json"
ALL_JOBS = rag_service.load_jobs_from_json(str(JOBS_PATH))

@app.on_event("startup")
async def startup():
    rag_service.ingest_jobs(ALL_JOBS)
    print(f"✅ Loaded {len(ALL_JOBS)} jobs into ChromaDB")

@app.get("/")
def root():
    return {"status": "ok", "service": "CareerFlow AI"}

@app.post("/api/resume/analyze")
async def analyze_resume(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files allowed")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 5MB)")
    try:
        text = pdf_service.extract_text_from_pdf(raw)
        if not text:
            raise HTTPException(400, "Could not extract text from PDF")
        profile_data = ai_service.analyze_resume(text)
        return {"profile": profile_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {e}")

@app.post("/api/jobs/match")
async def match_jobs(payload: ProfilePayload):
    profile = payload.profile.model_dump()
    jobs = matching_service.match_jobs(profile, ALL_JOBS, top_n=5)
    return {"jobs": jobs}

@app.post("/api/skills/gap")
async def skill_gap(payload: JobTargetPayload):
    profile = payload.profile.model_dump()
    job = next((j for j in ALL_JOBS if j["id"] == payload.job_id), None)
    if not job:
        raise HTTPException(404, "Job not found")
    gaps = ai_service.generate_skill_gap(profile, job)
    return {"target_role": job["title"], "gaps": gaps}

@app.post("/api/learning-plan")
async def learning_plan(payload: JobTargetPayload):
    profile = payload.profile.model_dump()
    job = next((j for j in ALL_JOBS if j["id"] == payload.job_id), None)
    if not job:
        raise HTTPException(404, "Job not found")
    gaps = ai_service.generate_skill_gap(profile, job)
    plan = ai_service.generate_learning_plan(profile, job, gaps)
    return {"plan": plan}

@app.post("/api/resume/improve")
async def improve_resume(payload: JobTargetPayload):
    profile = payload.profile.model_dump()
    job = next((j for j in ALL_JOBS if j["id"] == payload.job_id), None)
    if not job:
        raise HTTPException(404, "Job not found")
    suggestions = ai_service.improve_resume(profile, job)
    return {"suggestions": suggestions}

@app.post("/api/interview/start")
async def start_interview(payload: InterviewStartPayload):
    profile = payload.profile.model_dump()
    question = ai_service.generate_interview_question(profile, payload.job_title)
    return {"question": question}

@app.post("/api/interview/evaluate")
async def evaluate(payload: InterviewEvalPayload):
    result = ai_service.evaluate_interview_answer(
        payload.question, payload.answer, payload.job_title
    )
    return result