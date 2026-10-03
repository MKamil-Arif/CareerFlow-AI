"""CareerFlow AI — FastAPI application.

Run locally:   python -m uvicorn app.main:app --app-dir backend --reload
In Docker:     see the Dockerfile at the repository root.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router
from app.config import REPO_ROOT, settings
from app.core.security import SecurityHeadersMiddleware
from app.services import knowledge, search_service

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("careerflow")

FRONTEND_DIR = REPO_ROOT / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    jobs = knowledge.jobs()
    search = search_service.status()  # builds the in-memory index once
    log.info("CareerFlow AI %s starting (%s mode)", __version__, settings.app_env)
    log.info("Loaded %d curated jobs; search index has %d documents", len(jobs), search["documents"])
    if settings.ai_configured:
        log.info("AI providers: groq=%s (%s), gemini=%s (%s)",
                 bool(settings.groq_api_key), settings.groq_model, bool(settings.gemini_api_key), settings.gemini_model)
    else:
        log.warning("No AI provider key set — every feature will use its offline fallback.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="CareerFlow AI",
        version=__version__,
        description="Resume analysis, curated job matching, skill gaps, learning plans and interview practice. Stateless API.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    origins = ["http://127.0.0.1:5500", "http://localhost:5500"] if not settings.is_production else []
    origins += settings.cors_origins
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type"],
        )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = f"Invalid input{f' in {where}' if where else ''}: {first.get('msg', 'please check your data')}."
        return JSONResponse(status_code=422, content={"detail": message})

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Please try again."})

    app.include_router(router)

    # Serve the static frontend from the same origin (no CORS needed).
    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    else:
        log.warning("Frontend folder not found at %s; serving the API only.", FRONTEND_DIR)
    return app


app = create_app()
