from __future__ import annotations

from src.model.predict import score_comments
from src.recommender.candidate_generator import generate_candidates
from src.recommender.safety_filter import filter_safe_comments


def recommend_comments_with_meta(
    post_text: str,
    *,
    top_k: int = 5,
    category: str = "auto",
) -> dict:
    candidates = generate_candidates(
        post_text,
        category=category,
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
    top_k: int = 5,
    category: str = "auto",
) -> list[dict]:
    return recommend_comments_with_meta(
        post_text,
        top_k=top_k,
        category=category,
    )["recommendations"]


if __name__ == "__main__":
    result = recommend_comments(
        post_text="AI 시대에 개발자는 어떻게 살아남아야 할까?",
        top_k=5,
        category="social",
    )

    print("추천 댓글 결과")
    for row in result:
        print(f"\n[{row['rank']}] {row['type']} / 점수: {row['predicted_score']}")
        print(f"댓글: {row['comment']}")
