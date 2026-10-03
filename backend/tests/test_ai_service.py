import pytest

from app.services import ai_service


def test_extract_json_handles_fences_and_prose():
    assert ai_service.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai_service.extract_json('Sure! Here it is: [1, 2] thanks') == [1, 2]
    with pytest.raises(ValueError):
        ai_service.extract_json("no json here")


def test_no_keys_means_unavailable():
    with pytest.raises(ai_service.AIUnavailable):
        ai_service.complete("hi")


def test_gemini_is_used_when_groq_fails(monkeypatch):
    from app.config import settings
    object.__setattr__(settings, "groq_api_key", "test-groq")
    object.__setattr__(settings, "gemini_api_key", "test-gemini")
    try:
        def broken(*args):
            raise RuntimeError("401 invalid key")
        monkeypatch.setattr(ai_service, "_call_groq", broken)
        monkeypatch.setattr(ai_service, "_call_gemini", lambda *a: "Gemini fallback worked")
        assert ai_service.complete("test") == "Gemini fallback worked"
    finally:
        object.__setattr__(settings, "groq_api_key", "")
        object.__setattr__(settings, "gemini_api_key", "")


def test_invalid_ai_json_raises_so_routes_can_fall_back(monkeypatch):
    monkeypatch.setattr(ai_service, "complete", lambda *a, **k: "I cannot help with that")
    with pytest.raises(ValueError):
        ai_service.analyze_resume("some resume text")
    monkeypatch.setattr(ai_service, "complete", lambda *a, **k: '{"tasks": [{"title": "x"}]}')
    with pytest.raises(ValueError):
        ai_service.learning_plan({"skills": []}, {"title": "Dev"}, ["SQL"], [])


def test_ai_scores_are_clamped(monkeypatch):
    monkeypatch.setattr(ai_service, "complete", lambda *a, **k: '{"correctness": 14, "completeness": -2, "clarity": "7", "feedback": "ok"}')
    result = ai_service.evaluate_answer("q", "a", "Dev")
    assert (result["correctness"], result["completeness"], result["clarity"]) == (10, 0, 7)


def test_provider_responses_are_parsed(monkeypatch):
    from app.config import settings
    object.__setattr__(settings, "groq_model", "openai/gpt-oss-120b")
    sent = []

    def fake_post(url, headers, body):
        sent.append((url, body))
        if "groq" in url:
            if "reasoning_effort" in body:
                raise RuntimeError("HTTP 400: unsupported parameter reasoning_effort")
            return {"choices": [{"message": {"content": " hello "}}]}
        return {"candidates": [{"content": {"parts": [{"text": "thinking…", "thought": True}, {"text": "from gemini"}]}}]}

    monkeypatch.setattr(ai_service, "_post", fake_post)
    assert ai_service._call_groq("hi", 10, 0.1) == "hello"
    assert "reasoning_effort" not in sent[-1][1]  # retried without the optional parameter
    assert ai_service._call_gemini("hi", 10, 0.1) == "from gemini"
    assert sent[-1][0].endswith(":generateContent")
