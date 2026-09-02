from __future__ import annotations

import os

from src.llm.gemini_client import DEFAULT_GEMINI_MODEL, GeminiInteractionsClient
from src.llm.ollama_client import DEFAULT_OLLAMA_MODEL, OllamaChatClient
from src.llm.openai_client import LLMNotReadyError, OpenAIResponsesClient

SUPPORTED_FALLBACK_PROVIDERS = {"ollama", "gemini"}


def _openai_configured() -> bool:
    return bool((os.getenv("OPENAI_API_KEY") or "").strip()) and bool(
        (os.getenv("OPENAI_MODEL") or "").strip()
    )


def _fallback_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()


def _fallback_model(provider: str) -> str:
    configured = (os.getenv("LLM_MODEL") or "").strip()
    if configured:
        return configured
    if provider == "ollama":
        return DEFAULT_OLLAMA_MODEL
    if provider == "gemini":
        return DEFAULT_GEMINI_MODEL
    return ""


def llm_readiness() -> dict:
    if _openai_configured():
        return {
            "ready": True,
            "provider": "openai_responses_api",
            "selection": "openai",
            "model": (os.getenv("OPENAI_MODEL") or "").strip(),
            "missing": [],
        }

    provider = _fallback_provider()
    model = _fallback_model(provider)
    supported = provider in SUPPORTED_FALLBACK_PROVIDERS
    missing = []
    if not supported:
        missing.append("LLM_PROVIDER=supported provider")
    if not model:
        missing.append("LLM_MODEL")

    if provider == "gemini" and not (os.getenv("LLM_API_KEY") or "").strip():
        missing.append("LLM_API_KEY")

    ready = supported and bool(model) and not missing
    provider_name = {
        "ollama": "ollama_local",
        "gemini": "gemini_interactions_api",
    }.get(provider, provider)
    return {
        "ready": ready,
        "provider": provider_name,
        "selection": "fallback",
        "model": model or None,
        "missing": missing,
    }


def get_llm_client():
    if _openai_configured():
        return OpenAIResponsesClient()

    provider = _fallback_provider()
    model = _fallback_model(provider)
    if provider == "ollama":
        return OllamaChatClient(model=model)
    if provider == "gemini":
        return GeminiInteractionsClient(model=model)

    raise LLMNotReadyError(
        f"지원하지 않는 fallback LLM provider입니다: {provider or '(empty)'}"
    )
