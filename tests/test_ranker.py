import pytest

from src.llm.openai_client import LLMGenerationError
from src.recommender.ranker import recommend_comments_with_meta


def _batch(prefix: str, safe_count: int) -> list[dict]:
    items = []
    for index in range(10):
        if index < safe_count:
            comment = f"안전한 추천 댓글 {prefix}-{index} 입니다"
        else:
            comment = f"구독 부탁드립니다 {prefix}-{index}"
        items.append({"type": "general", "comment": comment})
    return items


def test_ranker_refills_after_safety_filter_reduces_pool_and_returns_trace(monkeypatch):
    batches = [_batch("first", 2), _batch("second", 5)]
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["minimum_count"])
        return batches[len(calls) - 1]

    monkeypatch.setattr("src.recommender.ranker.generate_candidates", fake_generate)
    monkeypatch.setattr(
        "src.recommender.ranker.score_comments",
        lambda post_text, comments: [
            {"comment": comment, "score": 90.0 - index}
            for index, comment in enumerate(comments)
        ],
    )

    result = recommend_comments_with_meta("reference", generation_context={}, top_k=5)

    assert len(calls) == 2
    assert len(result["recommendations"]) == 5
    assert result["candidate_count"] == 20
    assert result["safe_candidate_count"] == 7
    assert result["blocked_candidate_count"] == 13

    trace = result["trace"]
    assert len(trace["candidates"]) == 20
    assert trace["safety_blocked_count"] == 13
    assert trace["duplicate_candidate_count"] == 0
    assert sum(item["selected"] for item in trace["candidates"]) == 5
    assert sum(item["ranker_score"] is not None for item in trace["candidates"]) == 7
    blocked = [item for item in trace["candidates"] if item["safety"] == "blocked"]
    assert all(item["safety_reason"] == "spam" for item in blocked)
    assert all(item["ranker_score"] is None for item in blocked)


def test_ranker_marks_duplicate_candidate_before_ranking(monkeypatch):
    candidates = [
        {"type": "general", "comment": "첫 번째 안전한 댓글입니다"},
        {"type": "general", "comment": "첫 번째 안전한 댓글입니다"},
        {"type": "insight", "comment": "두 번째 안전한 댓글입니다"},
        {"type": "question", "comment": "세 번째 안전한 댓글입니다"},
        {"type": "casual", "comment": "네 번째 안전한 댓글입니다"},
        {"type": "empathy", "comment": "다섯 번째 안전한 댓글입니다"},
    ]
    monkeypatch.setattr("src.recommender.ranker.generate_candidates", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(
        "src.recommender.ranker.score_comments",
        lambda post_text, comments: [
            {"comment": comment, "score": 95.0 - index}
            for index, comment in enumerate(comments)
        ],
    )

    result = recommend_comments_with_meta("reference", generation_context={}, top_k=5)

    assert result["candidate_count"] == 6
    assert result["safe_candidate_count"] == 5
    assert result["trace"]["duplicate_candidate_count"] == 1
    duplicate = next(item for item in result["trace"]["candidates"] if item["duplicate"])
    assert duplicate["safety"] == "passed"
    assert duplicate["ranker_score"] is None
    assert duplicate["selected"] is False


def test_ranker_fails_instead_of_returning_partial_or_empty_result(monkeypatch):
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["minimum_count"])
        return _batch(f"attempt-{len(calls)}", 1)

    monkeypatch.setattr("src.recommender.ranker.generate_candidates", fake_generate)

    with pytest.raises(LLMGenerationError, match="안전 필터 통과 후보가 부족"):
        recommend_comments_with_meta("reference", generation_context={}, top_k=5)

    assert len(calls) == 3
