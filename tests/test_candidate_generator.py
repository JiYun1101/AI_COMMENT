import pytest

from src.recommender.candidate_generator import generate_candidates, infer_category


def test_candidates_are_context_aware_and_large_enough():
    candidates = generate_candidates(
        "제목: 제주도 3박 4일 먹방 여행 브이로그\n설명: 갈치조림과 동문시장을 다녀왔습니다.",
        category="vlog",
        minimum_count=10,
    )
    comments = [item["comment"] for item in candidates]

    assert len(candidates) >= 20
    assert len(comments) == len(set(comments))
    assert any("제주" in comment or "갈치" in comment or "동문" in comment for comment in comments)
    assert {item["type"] for item in candidates} >= {"insight", "empathy", "question", "casual", "general"}


def test_different_contexts_produce_different_comments():
    ai_comments = {
        item["comment"] for item in generate_candidates("제목: AI 시대 개발자 커리어 전략", category="social")
    }
    travel_comments = {
        item["comment"] for item in generate_candidates("제목: 제주 맛집 여행 브이로그", category="vlog")
    }
    assert ai_comments != travel_comments


@pytest.mark.parametrize(
    ("text", "expected"),
    [("제주 여행 브이로그 맛집 후기", "vlog"), ("AI 산업과 개발자 커리어 변화", "social")],
)
def test_infer_category(text, expected):
    assert infer_category(text) == expected


def test_invalid_category_is_rejected():
    with pytest.raises(ValueError):
        generate_candidates("테스트", category="unknown")
