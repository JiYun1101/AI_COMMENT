from __future__ import annotations

from src.model.predict import score_comments
from src.recommender.candidate_generator import generate_candidates
from src.recommender.safety_filter import filter_safe_comments


def recommend_comments_with_meta(
    post_text: str,
    *,
    generation_context: dict,
    top_k: int = 5,
) -> dict:
    candidates = generate_candidates(
        generation_context,
        minimum_count=max(top_k, 10),
    )
    safe_candidates = filter_safe_comments(candidates)

    comments = [item["comment"] for item in safe_candidates]
    if not comments:
        return {
            "recommendations": [],
            "candidate_count": len(candidates),
            "safe_candidate_count": 0,
            "blocked_candidate_count": len(candidates),
        }

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
        "candidate_count": len(candidates),
        "safe_candidate_count": len(safe_candidates),
        "blocked_candidate_count": len(candidates) - len(safe_candidates),
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
