"""[Optional] Comment Writer 그래프의 LLM 팩토리.

기본 제공자는 로컬 Ollama 이며, 환경변수 ``LLM_PROVIDER`` 로 교체한다.
어떤 제공자를 고르든 반환 객체는 아래 인터페이스를 만족한다::

    client.generate(generation_context, *, candidate_count, comment_type=None, feedback=None)

Official document URL:
    - Models: https://docs.langchain.com/oss/python/langchain/models
"""

from __future__ import annotations

import os

from src.llm.base import LLMNotReadyError
from src.llm.ollama_client import OllamaCommentClient, ollama_readiness
from src.llm.openai_client import OpenAIResponsesClient, llm_readiness

DEFAULT_PROVIDER = "ollama"

_PROVIDER_ALIASES = {
    "ollama": "ollama",
    "local": "ollama",
    "openai": "openai",
    "openai_responses": "openai",
}


def resolve_provider(provider: str | None = None) -> str:
    """제공자 이름을 정규화한다."""
    raw = (provider or os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    resolved = _PROVIDER_ALIASES.get(raw)
    if resolved is None:
        raise LLMNotReadyError(
            f"알 수 없는 LLM_PROVIDER 입니다: {raw!r} (사용 가능: ollama, openai)"
        )
    return resolved


def get_comment_generation_client(provider: str | None = None):
    """댓글 후보 생성을 담당할 LLM 클라이언트를 만든다.

    Args:
        provider: ``"ollama"`` 또는 ``"openai"``. 생략하면 ``LLM_PROVIDER`` 환경변수.

    Returns:
        생성 클라이언트 인스턴스.
    """
    resolved = resolve_provider(provider)
    if resolved == "ollama":
        return OllamaCommentClient()
    return OpenAIResponsesClient()


def comment_generation_readiness(provider: str | None = None) -> dict:
    """현재 설정으로 댓글 생성이 가능한지 점검한다 (``/health`` 용)."""
    try:
        resolved = resolve_provider(provider)
    except LLMNotReadyError as exc:
        return {"ready": False, "provider": None, "model": None, "missing": ["LLM_PROVIDER"], "detail": str(exc)}

    return ollama_readiness() if resolved == "ollama" else llm_readiness()
