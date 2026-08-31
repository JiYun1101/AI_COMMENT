from __future__ import annotations

from typing import Protocol

from src.llm.openai_client import LLMGenerationError
from src.llm.provider import get_llm_client


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
    candidates = provider.generate(generation_context, candidate_count=target_pool_size)
    if len(candidates) < minimum_count:
        raise LLMGenerationError(f"LLM 후보 수가 부족합니다 ({len(candidates)}/{minimum_count}).")
    return candidates
