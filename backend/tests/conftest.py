"""Tests never call real AI providers: keys are blanked before the app loads."""
import os

for _name in ("GROQ_API_KEY", "GEMINI_API_KEY"):
    os.environ[_name] = ""
os.environ.setdefault("RATE_LIMIT_AI_PER_MINUTE", "1000")
os.environ.setdefault("RATE_LIMIT_DEFAULT_PER_MINUTE", "1000")
