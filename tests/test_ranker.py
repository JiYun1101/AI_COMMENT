import pytest

from src.llm.openai_client import LLMGenerationError
from src.recommender.ranker import recommend_comments_with_meta


def _batch(prefix: str, safe_count: int) -> list[dict]:
    items = []
    for index in range(10):
        kind = "safe" if index < safe_count else "blocked"
        items.append({"type": "general", "comment": f"{kind}-{prefix}-{index}"})
    return items


def test_ranker_refills_after_safety_filter_reduces_pool(monkeypatch):
    batches = [_batch("first", 2), _batch("second", 5)]
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["minimum_count"])
        return batches[len(calls) - 1]

    monkeypatch.setattr("src.recommender.ranker.generate_candidates", fake_generate)
    monkeypatch.setattr(
        "src.recommender.ranker.filter_safe_comments",
        lambda candidates: [item for item in candidates if item["comment"].startswith("safe-")],
    )
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


def test_ranker_fails_instead_of_returning_partial_or_empty_result(monkeypatch):
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["minimum_count"])
        return _batch(f"attempt-{len(calls)}", 1)

    monkeypatch.setattr("src.recommender.ranker.generate_candidates", fake_generate)
    monkeypatch.setattr(
        "src.recommender.ranker.filter_safe_comments",
        lambda candidates: [item for item in candidates if item["comment"].startswith("safe-")],
    )

    with pytest.raises(LLMGenerationError, match="안전 필터 통과 후보가 부족"):
        recommend_comments_with_meta("reference", generation_context={}, top_k=5)

    assert len(calls) == 3
