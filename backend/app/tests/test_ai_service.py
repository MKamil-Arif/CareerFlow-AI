from types import SimpleNamespace
from app.services import ai_service

def test_gemini_is_used_when_groq_fails(monkeypatch):
    class GroqResponse:
        def create(self, **kwargs):
            raise RuntimeError("offline")
    failed_groq = SimpleNamespace(chat=SimpleNamespace(completions=GroqResponse()))
    monkeypatch.setattr(ai_service, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(ai_service, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(ai_service, "Groq", lambda **kwargs: failed_groq)
    import google.genai
    class Interactions:
        def create(self, **kwargs):
            return SimpleNamespace(output_text="Gemini fallback worked")
    fake_client = SimpleNamespace(interactions=Interactions())
    monkeypatch.setattr(google.genai, "Client", lambda **kwargs: fake_client)
    result = ai_service._client().chat.completions.create(messages=[{"role":"user","content":"test"}])
    assert result.choices[0].message.content == "Gemini fallback worked"
