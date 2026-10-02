# CareerFlow AI

From Profile to Job Readiness. A local single-user career planning MVP built with vanilla HTML/CSS/JavaScript, FastAPI, SQLite/SQLAlchemy, ChromaDB, and Groq/Gemini.

## Features

- PDF resume validation, selectable-text extraction, structured profile analysis, and editable profile details.
- Conservative explicit-skill extraction if AI providers fail; extracted data remains reviewable.
- Curated sample job browsing and search, weighted 0–100 match scores, matched/missing skills, score breakdowns, and grounded explanations.
- Skill gaps, a seven-day learning plan with official documentation links, saved plans, and persisted completion checkboxes.
- Resume suggestions, text interview practice with a scoring rubric, and saved interview history.
- SQLite storage for the local profile, curated jobs, match records, learning plans, and interview sessions.
- Chroma collections for jobs, skills, careers, interviews, and learning. The default local hashing-vector baseline runs offline. Set CAREERFLOW_EMBEDDING_MODEL to a directory containing a local Sentence Transformers model to use dense embeddings; if Chroma itself is unavailable, curated jobs remain usable through lexical matching.

Included jobs are curated examples, not live vacancies. Availability is not verified. Match scores are guidance, not hiring probabilities. Interview feedback is for practice, not an employer assessment.

## Run on Windows PowerShell

From the repository root:

    py -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r backend\app\requirements.txt

Add provider keys to backend/app/.env. Use the blank backend/app/.env.example only if .env does not already exist. Groq is tried first and Gemini is the secondary provider. Keep .env private and never put keys in frontend files. Without provider access, curated jobs, matching, learning plans, and heuristic interview practice remain available.

Run from the repository root:

    uvicorn app.main:app --app-dir backend --reload

Open http://127.0.0.1:8000/. API docs are at http://127.0.0.1:8000/docs and health is at http://127.0.0.1:8000/api/health. Chroma indexing runs locally at startup and does not need to download a model. For dense embeddings, install backend/app/requirements-embeddings.txt, download a Sentence Transformers model separately, and set CAREERFLOW_EMBEDDING_MODEL to its local directory. Vector indexing failures are logged and do not block the API.

FastAPI serves the frontend and API from one origin. If you serve frontend/ separately, set window.CAREERFLOW_API_BASE before script.js to the backend URL.

## Data and privacy

SQLite is stored at backend/app/data/careerflow.db and Chroma at backend/app/data/chroma/. Both are ignored by Git. This MVP has no accounts or authentication and is intended for one local user. It stores the parsed profile and interview text for the workflow, but does not retain the uploaded PDF. Delete the local database and Chroma folder to remove local records.

## API highlights

- POST /api/resume/analyze (also /api/resume/upload)
- GET/PUT /api/profile
- GET /api/jobs, GET /api/jobs/{id}, POST /api/jobs/match
- GET/POST /api/skills/gap
- GET/POST /api/learning-plan, PUT /api/learning-plan/{plan_id}/progress
- POST /api/resume/improve
- POST /api/interview/start, POST /api/interview/evaluate, GET /api/interview/history

## Tests

    pip install -r backend\app\requirements-dev.txt
    python -m pytest backend\app\tests -q

Focused tests cover skill matching and score transparency. Manual journey: upload a selectable-text PDF under 5 MB, review and edit the profile, search and choose a role, inspect skill gaps, generate/check off a learning plan, request resume suggestions, practice an interview, then refresh the interview history.

## Project layout

- frontend/ — responsive single-page workflow.
- backend/app/main.py — API routes and startup orchestration.
- backend/app/models.py and database.py — SQLAlchemy models and SQLite persistence.
- backend/app/services/ — PDF extraction, AI workflows, matching, and Chroma retrieval.
- backend/app/data/ — curated jobs, skills, careers, interviews, and learning records.
- backend/app/tests/ — business logic tests.
