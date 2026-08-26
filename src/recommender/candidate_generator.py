from __future__ import annotations

from src.llm.openai_client import OpenAIResponsesClient


def generate_candidates(
    generation_context: dict,
    *,
    minimum_count: int = 10,
    client: OpenAIResponsesClient | None = None,
) -> list[dict]:
    """Generate candidates from deterministic context using the configured LLM.

    Context collection/classification and historical-comment retrieval happen before
    this function. This module intentionally contains no fixed sentence templates.
    """
    if minimum_count < 1:
        raise ValueError("minimum_count는 1 이상이어야 합니다.")

    provider = client or OpenAIResponsesClient()
    target_pool_size = min(30, max(20, minimum_count * 2))
    candidates = provider.generate(generation_context, candidate_count=target_pool_size)
    if len(candidates) < minimum_count:
        raise RuntimeError(f"LLM 후보 수가 부족합니다 ({len(candidates)}/{minimum_count}).")
    return candidates
