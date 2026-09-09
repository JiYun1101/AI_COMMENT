from __future__ import annotations

import logging
import time
from typing import Protocol

from src.llm.openai_client import LLMGenerationError
from src.llm.provider import get_llm_client

logger = logging.getLogger(__name__)


class CandidateGenerationClient(Protocol):
    def generate(self, context: dict, *, candidate_count: int) -> list[dict]: ...


def generate_candidates(
    generation_context: dict,
    *,
    minimum_count: int = 10,
    client: CandidateGenerationClient | None = None,
) -> list[dict]:
    """Generate candidates from deterministic context using the configured LLM.

    OpenAI remains the preferred provider when both ``OPENAI_API_KEY`` and
    ``OPENAI_MODEL`` are configured. Otherwise the generic ``LLM_*`` fallback
    configuration is used. Context collection/classification and historical-comment
    retrieval still happen before this function; this module contains no fixed
    sentence templates.
    """
    if minimum_count < 1:
        raise ValueError("minimum_count는 1 이상이어야 합니다.")

    provider = client or get_llm_client()
    target_pool_size = min(30, max(20, minimum_count * 2))

    # provider 호출은 요청 지연과 실패의 대부분을 차지한다. 세 구현이 공유하는
    # 이 경계 한 곳에서 계측하면 클라이언트마다 로깅을 중복하지 않아도 된다.
    provider_name = type(provider).__name__
    started_at = time.monotonic()
    try:
        candidates = provider.generate(generation_context, candidate_count=target_pool_size)
    except Exception as exc:
        logger.warning(
            "llm.generate.failed provider=%s requested=%d elapsed_ms=%d error=%s detail=%s",
            provider_name,
            target_pool_size,
            (time.monotonic() - started_at) * 1000,
            type(exc).__name__,
            exc,
        )
        raise

    logger.info(
        "llm.generate.ok provider=%s requested=%d returned=%d elapsed_ms=%d",
        provider_name,
        target_pool_size,
        len(candidates),
        (time.monotonic() - started_at) * 1000,
    )
    if len(candidates) < minimum_count:
        raise LLMGenerationError(f"LLM 후보 수가 부족합니다 ({len(candidates)}/{minimum_count}).")
    return candidates
