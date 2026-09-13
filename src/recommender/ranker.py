from __future__ import annotations

import logging
import os
import time

from src.llm.openai_client import LLMGenerationError
from src.model.predict import score_comments
from src.recommender.candidate_generator import generate_candidates
from src.recommender.safety_filter import get_block_reason

logger = logging.getLogger(__name__)

MAX_GENERATION_ATTEMPTS = 3
DEFAULT_TIME_BUDGET_SECONDS = 90.0


def _time_budget_seconds() -> float:
    """생성 재시도 전체에 허용할 시간(초).

    재시도 3회 × provider timeout이 직렬로 쌓이면 요청 하나가 몇 분씩 매달릴 수
    있다. 첫 시도는 항상 수행하고, 이후 재시도는 남은 예산이 있을 때만 한다.
    """
    raw = (os.getenv("RECOMMEND_TIME_BUDGET_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_TIME_BUDGET_SECONDS
    try:
        value = float(raw)
    except ValueError:
        logger.warning("ranker.invalid_time_budget value=%s", raw)
        return DEFAULT_TIME_BUDGET_SECONDS
    return value if value > 0 else DEFAULT_TIME_BUDGET_SECONDS


def _normalized_comment(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def recommend_comments_with_meta(
    post_text: str,
    *,
    generation_context: dict,
    top_k: int = 5,
) -> dict:
    safe_candidates: list[dict] = []
    seen_safe: set[str] = set()
    trace_candidates: list[dict] = []
    trace_by_normalized: dict[str, dict] = {}
    candidate_count = 0
    safety_blocked_count = 0
    duplicate_candidate_count = 0
    budget = _time_budget_seconds()
    started_at = time.monotonic()
    budget_exhausted = False

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        elapsed = time.monotonic() - started_at
        if attempt > 1 and elapsed >= budget:
            budget_exhausted = True
            logger.warning(
                "ranker.budget_exhausted attempt=%d elapsed_ms=%d budget_ms=%d safe=%d",
                attempt,
                elapsed * 1000,
                budget * 1000,
                len(safe_candidates),
            )
            break

        candidates = generate_candidates(
            generation_context,
            minimum_count=max(top_k, 10),
        )
        candidate_count += len(candidates)

        for candidate in candidates:
            comment = str(candidate.get("comment") or "")
            normalized = _normalized_comment(comment)
            block_reason = get_block_reason(comment)
            trace_item = {
                "sequence": len(trace_candidates) + 1,
                "attempt": attempt,
                "type": candidate.get("type", "general"),
                "comment": comment,
                "safety": "blocked" if block_reason else "passed",
                "safety_reason": block_reason,
                "duplicate": False,
                "ranker_score": None,
                "selected": False,
                "final_rank": None,
            }

            if block_reason is not None:
                safety_blocked_count += 1
                trace_candidates.append(trace_item)
                continue

            if not normalized or normalized in seen_safe:
                duplicate_candidate_count += 1
                trace_item["duplicate"] = True
                trace_candidates.append(trace_item)
                continue

            seen_safe.add(normalized)
            safe_candidates.append(candidate)
            trace_candidates.append(trace_item)
            trace_by_normalized[normalized] = trace_item

        logger.info(
            "ranker.attempt attempt=%d generated=%d safe_total=%d blocked_total=%d duplicates=%d elapsed_ms=%d",
            attempt,
            len(candidates),
            len(safe_candidates),
            safety_blocked_count,
            duplicate_candidate_count,
            (time.monotonic() - started_at) * 1000,
        )

        if len(safe_candidates) >= top_k:
            break

    if len(safe_candidates) < top_k:
        reason = (
            "생성 시간 예산을 초과했습니다."
            if budget_exhausted
            else "새 후보 생성에 실패했습니다."
        )
        raise LLMGenerationError(
            f"안전 필터 통과 후보가 부족합니다 ({len(safe_candidates)}/{top_k}). {reason}"
        )

    comments = [item["comment"] for item in safe_candidates]
    scored_results = score_comments(post_text=post_text, comments=comments)
    comment_type_map = {
        item["comment"]: item.get("type", "general") for item in safe_candidates
    }

    recommendations = []
    for index, item in enumerate(scored_results[:top_k], start=1):
        recommendations.append(
            {
                "rank": index,
                "type": comment_type_map.get(item["comment"], "general"),
                "comment": item["comment"],
                "predicted_score": item["score"],
            }
        )

    final_rank_by_normalized = {
        _normalized_comment(item["comment"]): index
        for index, item in enumerate(scored_results[:top_k], start=1)
    }
    score_by_normalized = {
        _normalized_comment(item["comment"]): item["score"]
        for item in scored_results
    }
    for normalized, trace_item in trace_by_normalized.items():
        trace_item["ranker_score"] = score_by_normalized.get(normalized)
        final_rank = final_rank_by_normalized.get(normalized)
        trace_item["selected"] = final_rank is not None
        trace_item["final_rank"] = final_rank

    return {
        "recommendations": recommendations,
        "candidate_count": candidate_count,
        "safe_candidate_count": len(safe_candidates),
        "blocked_candidate_count": candidate_count - len(safe_candidates),
        "trace": {
            "safety_blocked_count": safety_blocked_count,
            "duplicate_candidate_count": duplicate_candidate_count,
            "candidates": trace_candidates,
        },
    }


def recommend_comments(
    post_text: str,
    *,
    generation_context: dict,
    top_k: int = 5,
) -> list[dict]:
    return recommend_comments_with_meta(
        post_text,
        generation_context=generation_context,
        top_k=top_k,
    )["recommendations"]
