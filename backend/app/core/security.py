"""Protections for running publicly: rate limiting and security headers."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class RateLimiter:
    """Sliding-window limit per client IP, kept in memory (resets on restart).

    Good enough for a single free-tier instance. If you later run several
    instances, move this to a shared store or your host's edge rate limiting.
    """

    def __init__(self, per_minute: int, window: float = 60.0):
        self.per_minute = per_minute
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        if self.per_minute <= 0:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.per_minute:
                retry = int(self.window - (now - hits[0])) + 1
                raise HTTPException(429, "Too many requests. Please wait a moment and try again.",
                                    headers={"Retry-After": str(retry)})
            hits.append(now)
            if len(self._hits) > 10_000:  # drop idle clients so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                    self._hits.pop(k, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


ai_limiter = RateLimiter(settings.rate_limit_ai_per_minute)
default_limiter = RateLimiter(settings.rate_limit_default_per_minute)


def client_ip(request: Request) -> str:
    # Uvicorn runs with --proxy-headers in Docker, so request.client is the real
    # visitor behind Render/Hugging Face proxies.
    return request.client.host if request.client else "unknown"


def limit_ai(request: Request) -> None:
    """Dependency for endpoints that may call a paid/limited AI provider."""
    ai_limiter.check(client_ip(request))


def limit_default(request: Request) -> None:
    default_limiter.check(client_ip(request))


CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers.setdefault("Content-Security-Policy", CSP)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
