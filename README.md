# CareerFlow AI

**From profile to job readiness.** Upload a PDF resume and CareerFlow AI builds an editable profile, suggests roles that fit *your* CV in any field (regenerate them, steer them with a preference, or type your own target role) with a transparent score, shows your skill gaps, creates a 7-day learning plan with official documentation links, suggests resume improvements, and lets you practise interview questions with scored feedback.

- **Frontend:** plain HTML, CSS and JavaScript (no build step)
- **Backend:** FastAPI (Python 3.10+), stateless
- **AI:** Groq first, Gemini as backup. Optional: with no keys every feature still works using offline rules.
- **No database.** Curated data is read from JSON files. Your profile, plans, progress and interview history stay in **your browser** (localStorage). Uploaded resumes are processed in memory and never saved.

> Jobs are curated examples, not live vacancies. Match scores and interview feedback are guidance, not hiring decisions.

## Run locally (Windows CMD or VS Code terminal)

**Easiest:** double-click `run.bat`. It sets up `.venv`, installs packages, checks your AI keys, starts the server and opens your browser.

Or run the steps yourself:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
copy .env.example .env
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Open http://127.0.0.1:8000 — API docs at `/docs`, health at `/api/health`.

macOS / Linux: the same commands with `python3 -m venv .venv` and `.venv/bin/python`.

### Turn on AI features

Put at least one key in `.env` (repository root), then check that it works:

```bat
cd backend
..\.venv\Scripts\python.exe -m app.check_ai
```

It prints `[ ok ]` or `[FAIL]` with the real error for each provider (bad key, wrong model name, blocked network). The server log also records every provider failure.

## Deploy (free)

The repo is ready for free hosting with the included `Dockerfile`:

| Platform | Free tier | How |
|---|---|---|
| **Render** (recommended) | 512 MB RAM, sleeps after 15 min idle, ~1 min wake-up | `render.yaml` blueprint |
| **Hugging Face Spaces** | Docker Space on free CPU hardware | Same Dockerfile |

Step-by-step instructions: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Tests

```bat
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe -m pytest
```

GitHub Actions (`.github/workflows/ci.yml`) runs the tests and a Docker build on every push.

## Project layout

```
careerflow-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # app factory, middleware, serves the frontend
│   │   ├── config.py            # all settings from environment variables
│   │   ├── schemas.py           # validated, size-limited request bodies
│   │   ├── check_ai.py          # `python -m app.check_ai` provider diagnostics
│   │   ├── api/routes.py        # REST endpoints (stateless)
│   │   ├── core/security.py     # rate limiting + security headers
│   │   ├── services/
│   │   │   ├── ai_service.py        # Groq/Gemini calls + prompts (logged failures)
│   │   │   ├── career_service.py    # offline parser, plans, questions, scoring
│   │   │   ├── matching_service.py  # weighted 0–100 match + skill gaps
│   │   │   ├── search_service.py    # in-memory TF-IDF search (replaces ChromaDB)
│   │   │   ├── skills.py            # skill aliases (ReactJS = React, …)
│   │   │   ├── knowledge.py         # loads the curated JSON data
│   │   │   └── pdf_service.py       # PDF text extraction
│   │   └── data/                # jobs, skills, careers, interviews, learning resources
│   ├── tests/
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/                    # index.html, script.js, style.css, config.js, theme.js
├── docs/DEPLOYMENT.md
├── Dockerfile · .dockerignore · render.yaml
└── .env.example
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status, AI configuration, search index size |
| POST | `/api/resume/analyze` | PDF upload → profile (`mode`: `ai` or `offline`) |
| POST | `/api/resume/improve` | Resume suggestions for a target job |
| GET | `/api/jobs`, `/api/jobs/{id}` | Curated roles (`?q=` and `?location=` filters) |
| POST | `/api/jobs/recommend` | Roles suggested from the CV (any field). `exclude` = titles already shown (for regenerate), `preference` = e.g. "remote finance" |
| POST | `/api/jobs/custom` | Build a target role from a typed title, scored against the profile |
| POST | `/api/jobs/match` | Score the curated catalog against a profile |
| POST | `/api/skills/gap` | `have` / `missing` (required) / `improve` (preferred) |
| POST | `/api/learning-plan` | 7-day plan with official resources |
| POST | `/api/interview/start` | Next question (technical → behavioral → scenario) |
| POST | `/api/interview/evaluate` | Scores 0–10 for correctness, completeness, clarity |

Requests that need a profile send it in the body. Skill gap, learning plan, resume tips and interview requests take the target role as `"job": {...}` (the full role object the browser received), or `"job_id"` for a catalog role, so Skill Gap → Learning → Interview always follow the role the user selected — without the server storing anything.

## Customising the data

Edit the JSON files in `backend/app/data/`. `jobs.json` is the offline role catalog (33 roles across marketing, finance, HR, sales, design, engineering, healthcare, education, admin and IT) used when AI is unavailable. Add a role to `jobs.json` (unique numeric `id`), and add a matching official resource to `learning.json` so learning plans link to it. Restart the server to reload.

## Privacy

- No accounts, no database, no server-side storage of resumes or profiles.
- Profile text is sent to the configured AI provider (Groq or Gemini) for analysis when keys are set.
- "Clear my data" in the app sidebar removes everything stored in the browser.
