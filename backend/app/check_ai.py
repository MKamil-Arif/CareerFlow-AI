"""Check that the configured AI providers actually answer.

    python -m app.check_ai            (run from the backend/ folder)
    .venv\\Scripts\\python.exe -m app.check_ai   (Windows, from backend\\)

Prints a clear pass/fail per provider with the real error, so a bad key, a
wrong model name or a blocked network is easy to spot. Keys are never printed.
"""
from __future__ import annotations

import sys

from app.config import settings
from app.services import ai_service

PROMPT = "Reply with the single word: ready"


def main() -> int:
    checks = [("Groq", settings.groq_api_key, settings.groq_model, ai_service._call_groq),
              ("Gemini", settings.gemini_api_key, settings.gemini_model, ai_service._call_gemini)]
    ok_any = False
    for name, key, model, call in checks:
        if not key:
            print(f"[skip] {name}: no API key set")
            continue
        try:
            answer = call(PROMPT, 20, 0.0)
            print(f"[ ok ] {name} ({model}) answered: {answer[:60]!r}")
            ok_any = True
        except Exception as exc:
            print(f"[FAIL] {name} ({model}): {type(exc).__name__}: {str(exc)[:400]}")
    if not ok_any:
        print("\nNo provider works. Check the key, the model name, and that this machine can reach the provider.")
        print("The app still runs with offline fallbacks.")
    return 0 if ok_any else 1


if __name__ == "__main__":
    sys.exit(main())
