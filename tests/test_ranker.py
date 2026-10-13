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


def test_default_recommendations_limit_repetitive_laughter_without_changing_scores(monkeypatch):
    marked = [
        "인트로 음악 선택 정말 묘하네요 ㅋㅋ",
        "이번 영상에서 설명한 방법은 실용적이네요 ㅎㅎ",
        "영상 속 그림 구성이 흥미로운 것 같아요 ㅋㅋ",
        "중간에 등장한 장면이 인상적이네요 ㅋㅋ",
        "마지막 정리가 꽤 깔끔하다고 느꼈어요 ㅎㅎ",
    ]
    plain = [
        "주제를 구체적인 사례로 설명해서 좋습니다.",
        "영상 후반부의 결론에서 생각할 지점이 많네요.",
        "이 내용은 실생활에서 어떻게 응용하나요?",
        "다음 영상에서는 반대 사례도 다뤄주실 수 있나요?",
        "비슷한 상황에서 쓰는 팁이 궁금해집니다.",
    ]
    candidates = [{"type": "general", "comment": text} for text in marked + plain]
    monkeypatch.setattr("src.recommender.ranker.generate_candidates", lambda *a, **kw: candidates)
    monkeypatch.setattr(
        "src.recommender.ranker.score_comments",
        lambda post_text, comments: [
            {"comment": comment, "score": 100 - index * 3}
            for index, comment in enumerate(comments)
        ],
    )
    output = recommend_comments_with_meta("영상", generation_context={}, top_k=5)
    selected = output["recommendations"]
    assert len(selected) == 5
    assert sum("ㅋㅋ" in r["comment"] or "ㅎㅎ" in r["comment"] for r in selected) <= 1
    assert selected[0]["comment"] == "인트로 음악 선택 정말 묘하네요"
    # Selected results retain raw ranker scores, not fabricated adjusted probabilities.
    assert selected[0]["predicted_score"] == 100
    assert sum(item["selected"] for item in output["trace"]["candidates"]) == 5
    assert [item["final_rank"] for item in output["trace"]["candidates"] if item["selected"]] != []


def test_playful_persona_keeps_some_laughter_without_flooding_results(monkeypatch):
    from src.recommender.ranker import _select_diverse_results
    comments = [
        "도입부에서 나온 장면 너무 귀엽네 ㅋㅋ",
        "후반부 영상의 연출이 꽤 재밌다 ㅎㅎ",
        "이 장면의 색깔 조합이 특이하다 ㅋㅋ",
        "배경 음악이 몽환적인 느낌이다 ㅎㅎ",
        "대사의 의미가 흥미롭다고 느꼈어 ㅋㅋ",
        "여기서 등장한 반전이 정말 신선하네",
        "이 영상에서 중요한 주제는 뭘까?",
        "비슷한 사례를 더 보고 싶다",
    ]
    scored = [{"comment": text, "score": 100 - i} for i, text in enumerate(comments)]
    result = _select_diverse_results(scored, 5, {"id": "playful_casual"})
    assert len(result) == 5
    assert sum("ㅋㅋ" in row["comment"] or "ㅎㅎ" in row["comment"] for row in result) == 2


def test_identical_substance_with_or_without_laughter_is_near_duplicate():
    from src.recommender.ranker import _too_similar
    assert _too_similar(
        "자막 설명이 자세해서 이해하기 쉬워요 ㅋㅋ",
        "자막 설명이 자세해서 이해하기 쉬워요",
    )
    assert not _too_similar(
        "영상 초반에는 주제를 짧게 소개하고 있어요",
        "다음 영상에서 실험 결과도 볼 수 있을까요",
    )


def test_diversity_falls_back_when_provider_returns_only_laughter(monkeypatch):
    from src.recommender.ranker import _select_diverse_results
    rows = [
        {"comment": "주제 정리 정말 깔끔했네요 ㅋㅋ" + str(i), "score": 100 - i}
        for i in range(5)
    ]
    assert len(_select_diverse_results(rows, 5, None)) == 5
