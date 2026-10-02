"""CareerFlow AI REST API."""
import re
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.schemas import ProfilePayload, JobTargetPayload, InterviewStartPayload, InterviewEvalPayload, Profile
from app.database import init_db, save_profile, get_profile, save_plan, save_match, create_interview, evaluate_interview, interview_history, seed_jobs, get_latest_plan, update_plan_progress
from app.services import pdf_service, ai_service, rag_service, matching_service

app = FastAPI(title="CareerFlow AI", version="1.0.0", description="Career profile, curated job matching, skill planning, and interview practice.")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:8000", "http://localhost:8000"], allow_methods=["GET", "POST", "PUT", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])
JOBS_PATH = Path(__file__).parent / "data" / "jobs.json"
ALL_JOBS = rag_service.load_jobs_from_json(str(JOBS_PATH))

@app.on_event("startup")
async def startup():
    init_db()
    seed_jobs(ALL_JOBS)
    try:
        result = rag_service.ingest_knowledge()
        print(f"CareerFlow knowledge index: {result}")
    except Exception as exc:
        print(f"CareerFlow started without vector indexing: {type(exc).__name__}")

@app.get("/")
def root():
    return FileResponse(FRONTEND_PATH / "index.html")

@app.get("/api/health")
def health():
    try: rag = rag_service.status()
    except Exception: rag = {"available":False}
    return {"status":"ok", "database":"sqlite", "rag":rag, "ai":"configured" if __import__("app.config", fromlist=["GROQ_API_KEY"]).GROQ_API_KEY or __import__("app.config", fromlist=["GEMINI_API_KEY"]).GEMINI_API_KEY else "offline fallback"}

@app.post("/api/resume/upload")
@app.post("/api/resume/analyze")
async def analyze_resume(file: UploadFile = File(...)):
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Upload a PDF resume.")
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024: raise HTTPException(413, "Resume is larger than the 5 MB limit.")
    if not raw.startswith(b"%PDF"):
        raise HTTPException(400, "This file does not contain a readable PDF document.")
    try:
        text = pdf_service.extract_text_from_pdf(raw)
    except ValueError:
        raise HTTPException(400, "The PDF is damaged or could not be read. Please export it again and retry.")
    if len(text.strip()) < 20:
        raise HTTPException(422, "No selectable text was found. Scanned image-only PDFs are not supported yet.")
    try:
        data = ai_service.analyze_resume(text)
    except Exception:
        catalog = sorted({s for job in ALL_JOBS for s in job.get("required_skills", []) + job.get("preferred_skills", [])}, key=len, reverse=True)
        skills = [s for s in catalog if re.search(r"(?<![\w+#])" + re.escape(s) + r"(?![\w+#])", text, re.I)]
        data = {"name":"", "skills":skills, "experience":[], "education":[], "projects":[], "certifications":[], "location":"", "career_level":"Entry"}
        data["analysis_note"] = "AI provider unavailable; only explicit job-catalog skills were extracted. Review and edit this profile."
    try:
        data = Profile.model_validate(data).model_dump()
    except Exception:
        data = {"name":"", "skills":[], "experience":[], "education":[], "projects":[], "certifications":[], "location":"", "career_level":"Entry", "analysis_note":"The profile response was invalid. Please review or edit it."}
    save_profile(data)
    return {"profile":data, "analysis_mode":"AI or conservative extraction"}

@app.get("/api/profile")
def profile_get():
    value = get_profile()
    if value is None: raise HTTPException(404, "No saved profile yet.")
    return {"profile":value}

@app.put("/api/profile")
def profile_update(payload: ProfilePayload):
    return {"profile":save_profile(payload.profile)}

@app.get("/api/jobs")
def jobs_list(q: str = Query(default="", max_length=120), location: str = Query(default="", max_length=120)):
    rows = ALL_JOBS
    if q:
        terms = q.casefold().split()
        rows = [j for j in rows if any(t in (j.get("title","")+" "+j.get("description","")+" "+" ".join(j.get("required_skills",[]))).casefold() for t in terms)]
    if location:
        rows = [j for j in rows if location.casefold() in j.get("location","").casefold() or "remote" in j.get("location","").casefold()]
    return {"jobs":rows, "notice":"Curated sample roles; vacancy status has not been verified."}

@app.get("/api/jobs/{job_id}")
def job_get(job_id: int):
    job = next((j for j in ALL_JOBS if j["id"] == job_id), None)
    if not job: raise HTTPException(404, "Job not found.")
    return {"job":job}

@app.post("/api/jobs/match")
def match_jobs(payload: ProfilePayload):
    prof = save_profile(payload.profile)
    results = matching_service.match_jobs(prof, ALL_JOBS, top_n=100)
    for row in results: save_match(row["id"], row["match"], row)
    return {"jobs":results, "weights":matching_service.WEIGHTS, "notice":"Scores are weighted guidance, not hiring probabilities. Roles are curated examples, not verified openings."}

def _fallback_plan(profile, job, gaps):
    targets = gaps["missing"] or ["Practice " + s for s in gaps["improve"]] or ["portfolio project"]
    resources = {"Python": ("Python tutorial", "https://docs.python.org/3/tutorial/"), "JavaScript": ("MDN JavaScript guide", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"), "React": ("React Learn", "https://react.dev/learn"), "SQL": ("SQLite SQL language", "https://www.sqlite.org/lang.html"), "HTML": ("MDN HTML guide", "https://developer.mozilla.org/en-US/docs/Learn/HTML"), "CSS": ("MDN CSS guide", "https://developer.mozilla.org/en-US/docs/Learn/CSS")}
    rows=[]
    for i in range(7):
        skill=targets[i % len(targets)]; title,url=resources.get(skill,("Guided practice: "+skill,""))
        rows.append({"day":f"Day {i+1}","title":f"Practice {skill}","skill":skill,"desc":f"Study {skill}, then apply it to a small task relevant to {job['title']}.","completion_criteria":f"Finish one exercise and save a working example of {skill}.","resource_title":title,"resource_url":url})
    return rows

def _job(job_id):
    found = next((j for j in ALL_JOBS if j["id"] == job_id), None)
    if not found: raise HTTPException(404, "Job not found.")
    return found

def _gaps(profile, job):
    known = {s.casefold() for s in profile.get("skills", [])}
    have = [s for s in job.get("required_skills", []) if s.casefold() in known]
    missing = [s for s in job.get("required_skills", []) if s.casefold() not in known]
    improve = [s for s in job.get("preferred_skills", []) if s.casefold() in known]
    not_demonstrated = [s for s in job.get("preferred_skills", []) if s.casefold() not in known]
    return {"have":have, "improve":improve, "missing":missing, "not_demonstrated_preferred":not_demonstrated, "missing_label":"Not demonstrated in the provided profile", "reasons":{s:f"{s} is listed as a requirement for {job['title']}." for s in missing}}

@app.post("/api/skills/gap")
def skill_gap(payload: JobTargetPayload):
    profile = save_profile(payload.profile)
    job = _job(payload.job_id)
    return {"target_role":job["title"], "job":job, "gaps":_gaps(profile,job)}

@app.get("/api/skills/gap")
def skill_gap_get(job_id: int, profile_id: int = 1):
    profile = get_profile()
    if not profile: raise HTTPException(404,"Analyze or save a profile first.")
    job = _job(job_id)
    return {"target_role":job["title"],"job":job,"gaps":_gaps(profile,job)}

@app.get("/api/learning-plan")
def latest_learning_plan(job_id: int):
    saved=get_latest_plan(job_id)
    if not saved: raise HTTPException(404,"No saved plan for this role.")
    return saved

@app.put("/api/learning-plan/{plan_id}/progress")
def update_learning_progress(plan_id: int, completed: list[int]):
    if any(i < 0 or i > 6 for i in completed): raise HTTPException(422,"Task index must be between 0 and 6.")
    if not update_plan_progress(plan_id,completed): raise HTTPException(404,"Learning plan not found.")
    return {"saved":True,"completed":completed}

@app.post("/api/learning-plan")
def learning_plan(payload: JobTargetPayload):
    profile = save_profile(payload.profile)
    job = _job(payload.job_id)
    gaps = _gaps(profile,job)
    try: plan = ai_service.generate_learning_plan(profile,job,gaps)
    except Exception: plan = _fallback_plan(profile,job,gaps)
    plan_id = save_plan(job["id"], plan)
    return {"plan":plan,"plan_id":plan_id,"target_role":job["title"]}

@app.post("/api/resume/improve")
def improve_resume(payload: JobTargetPayload):
    profile = save_profile(payload.profile)
    try: suggestions = ai_service.improve_resume(profile,_job(payload.job_id))
    except Exception:
        suggestions = [{"area":"Projects","suggestion":"Describe a project you actually completed, including your contribution and verified outcome.","reason":"Makes evidence of skills concrete."},{"area":"Skills","suggestion":"Prioritize demonstrated skills that appear in this role requirements.","reason":"Improves relevance without adding new claims."}]
    return {"suggestions":suggestions,"grounding":"Suggestions must be checked against your actual experience; do not add claims you cannot verify."}

@app.post("/api/interview/start")
def start_interview(payload: InterviewStartPayload):
    profile = save_profile(payload.profile)
    title = payload.job_title
    job = _job(payload.job_id) if payload.job_id else next((j for j in ALL_JOBS if j["title"].casefold()==title.casefold()), None)
    if job: title = job["title"]
    context = ", ".join(job.get("required_skills", []) + job.get("preferred_skills", [])) if job else ""
    try:
        question = ai_service.generate_interview_question(profile, title, payload.previous, context)
    except Exception:
        question = f"Describe how you would approach a practical challenge in a {title} role. What steps would you take, and how would you verify your result?"
    sid = create_interview(title,question)
    return {"question":question,"session_id":sid,"notice":"Practice coaching only; not an official hiring assessment."}

@app.post("/api/interview/evaluate")
def evaluate(payload: InterviewEvalPayload):
    try: result = ai_service.evaluate_interview_answer(payload.question,payload.answer,payload.job_title)
    except Exception:
        words = len(payload.answer.split())
        score = max(2, min(8, 2 + words // 25))
        result = {"correctness":score,"completeness":score,"clarity":min(8,score+1),"feedback":"Offline practice rubric: add a specific example, explain your own actions, and state a result you can verify. Provider feedback is unavailable.","improved_answer":"Structure your response as context, your action, why you chose that approach, and the result.","rubric":{"correctness":"technical relevance (offline estimate)","completeness":"context, actions, and outcome","clarity":"organization and concise wording"}}
    sid = evaluate_interview(payload.session_id,payload.answer,result)
    return {**result,"session_id":sid,"notice":"Practice guidance only; scores are not an official hiring assessment."}

@app.get("/api/interview/history")
def interviews():
    return {"sessions":interview_history()}


# Serve the vanilla frontend from the same local FastAPI origin.
FRONTEND_PATH = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_PATH.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend")
