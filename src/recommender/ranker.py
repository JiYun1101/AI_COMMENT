from __future__ import annotations

from src.llm.openai_client import LLMGenerationError
from src.model.predict import score_comments
from src.recommender.candidate_generator import generate_candidates
from src.recommender.safety_filter import get_block_reason

MAX_GENERATION_ATTEMPTS = 3


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

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
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

        if len(safe_candidates) >= top_k:
            break

    if len(safe_candidates) < top_k:
        raise LLMGenerationError(
            f"안전 필터 통과 후보가 부족합니다 ({len(safe_candidates)}/{top_k}). 새 후보 생성에 실패했습니다."
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
