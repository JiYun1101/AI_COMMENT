from src.llm.gemini_client import GeminiInteractionsClient
from src.llm.openai_client import OpenAIResponsesClient
from src.llm.provider import get_llm_client, llm_readiness


def test_openai_configuration_has_priority(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "openai-model")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "gemini-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-3.7-flash")

    readiness = llm_readiness()
    client = get_llm_client()

    assert readiness["ready"] is True
    assert readiness["selection"] == "openai"
    assert readiness["provider"] == "openai_responses_api"
    assert isinstance(client, OpenAIResponsesClient)


def test_gemini_fallback_is_used_when_openai_is_empty(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "gemini-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-3.7-flash")

    readiness = llm_readiness()
    client = get_llm_client()

    assert readiness["ready"] is True
    assert readiness["selection"] == "fallback"
    assert readiness["provider"] == "gemini_interactions_api"
    assert readiness["model"] == "gemini-3.7-flash"
    assert isinstance(client, GeminiInteractionsClient)


def test_gemini_model_defaults_when_only_fallback_key_is_set(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "gemini-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    readiness = llm_readiness()

    assert readiness["ready"] is True
    assert readiness["model"] == "gemini-3.7-flash"
