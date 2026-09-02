from src.llm.gemini_client import GeminiInteractionsClient
from src.llm.ollama_client import OllamaChatClient
from src.llm.openai_client import OpenAIResponsesClient
from src.llm.provider import get_llm_client, llm_readiness


def _clear_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)


def test_openai_configuration_has_priority(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "openai-model")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")

    readiness = llm_readiness()
    client = get_llm_client()

    assert readiness["ready"] is True
    assert readiness["selection"] == "openai"
    assert readiness["provider"] == "openai_responses_api"
    assert isinstance(client, OpenAIResponsesClient)


def test_ollama_is_default_fallback_when_openai_is_empty(monkeypatch):
    _clear_openai(monkeypatch)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)

    readiness = llm_readiness()
    client = get_llm_client()

    assert readiness["ready"] is True
    assert readiness["selection"] == "fallback"
    assert readiness["provider"] == "ollama_local"
    assert readiness["model"] == "qwen3:8b"
    assert readiness["missing"] == []
    assert isinstance(client, OllamaChatClient)
    assert client.base_url == "http://localhost:11434"


def test_ollama_does_not_require_api_key(monkeypatch):
    _clear_openai(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    readiness = llm_readiness()

    assert readiness["ready"] is True
    assert "LLM_API_KEY" not in readiness["missing"]


def test_gemini_remains_available_as_optional_fallback(monkeypatch):
    _clear_openai(monkeypatch)
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


def test_gemini_still_requires_api_key(monkeypatch):
    _clear_openai(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    readiness = llm_readiness()

    assert readiness["ready"] is False
    assert readiness["model"] == "gemini-3.7-flash"
    assert "LLM_API_KEY" in readiness["missing"]
