from __future__ import annotations

from src.llm.openai_client import LLMGenerationError
from src.model.predict import score_comments
from src.recommender.candidate_generator import generate_candidates
from src.recommender.safety_filter import filter_safe_comments

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
    candidate_count = 0

    for _ in range(MAX_GENERATION_ATTEMPTS):
        candidates = generate_candidates(
            generation_context,
            minimum_count=max(top_k, 10),
        )
        candidate_count += len(candidates)
        batch_safe = filter_safe_comments(candidates)

        for candidate in batch_safe:
            normalized = _normalized_comment(str(candidate.get("comment") or ""))
            if not normalized or normalized in seen_safe:
                continue
            seen_safe.add(normalized)
            safe_candidates.append(candidate)

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

    return {
        "recommendations": recommendations,
        "candidate_count": candidate_count,
        "safe_candidate_count": len(safe_candidates),
        "blocked_candidate_count": candidate_count - len(safe_candidates),
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
