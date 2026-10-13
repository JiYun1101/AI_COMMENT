from src.recommender.writing_style import clean_comment, detect_style, casual_target
from src.recommender.ranker import _select_diverse_results
from src.llm.openai_client import build_generation_input, validate_candidates


def test_clean_output_preserves_readable_spacing_and_questions():
    assert clean_comment("넘 괜찮네   😄ㅋㅋㅋㅋ!!!") == "넘 괜찮네"
    assert clean_comment("얼마야?") == "얼마야?"
    assert clean_comment("가격이 3.5만원이라 그런 듯.") == "가격이 3.5만원이라 그런 듯"
    assert detect_style("이거 좀 신기함") == "casual_imperfect"


def test_generation_budget_is_half_chatty_except_formal():
    context = {"historical_comments": {"reference_examples": []}}
    assert build_generation_input(context, candidate_count=20)["task"]["writing_style_counts"] == {
        "casual_imperfect": 10, "standard": 10,
    }
    assert build_generation_input(
        context, candidate_count=20, persona={"id": "polite_viewer"},
    )["task"]["writing_style_counts"]["casual_imperfect"] == 0
    assert casual_target(5) == 2
    assert casual_target(10) == 5


def test_candidate_validation_keeps_style_and_cleans_punctuation():
    payload = {"candidates": [
        {"type": "casual", "writing_style": "casual_imperfect", "comment": "갠적으로 여기 재밌음 😄."},
        {"type": "question", "writing_style": "standard", "comment": "다음 편은 언제 나오나요?"},
        {"type": "general", "comment": "완전 신기함!!!"},
    ]}
    result = validate_candidates(payload, minimum_count=3)
    assert result[0]["writing_style"] == "casual_imperfect"
    assert result[0]["comment"] == "갠적으로 여기 재밌음"
    assert result[1]["comment"] == "다음 편은 언제 나오나요?"
    assert result[2]["writing_style"] == "casual_imperfect"
    assert result[2]["comment"] == "완전 신기함"


def test_top_k_uses_two_chatty_and_three_standard_when_pool_supports_it():
    comments = [
        ("다음 영상에서 반대 의견도 소개해주실 수 있나요?", "standard"),
        ("전체적으로 설명이 구체적이라 이해하기 편했어요", "standard"),
        ("주제를 풀어내는 전개가 꽤 매끄럽네요", "standard"),
        ("이런 점은 처음 알았어요 좋은 설명이에요", "standard"),
        ("왜케 이 장면 좀 재밌음", "casual_imperfect"),
        ("갠적으로 마지막 장면 넘 좋음", "casual_imperfect"),
        ("먼가 이런 연출 맘에 듬", "casual_imperfect"),
    ]
    rows = [{"comment": value, "score": 100-i} for i, (value, _) in enumerate(comments)]
    styles = {text: name for text, name in comments}
    result = _select_diverse_results(rows, 5, None, styles)
    assert len(result) == 5
    assert sum(styles[row["comment"]] == "casual_imperfect" for row in result) == 2
    assert [row["score"] for row in result] == sorted([row["score"] for row in result], reverse=True)
    assert result[0]["score"] == 100


def test_formal_persona_prefers_standard_and_shortage_falls_back():
    rows = [
        {"comment": "먼가 이런 장면 첨 봄", "score": 99},
        {"comment": "넘 재밌게 봤음", "score": 98},
        {"comment": "정리된 설명이 인상 깊었습니다", "score": 97},
        {"comment": "내용을 구체적으로 비교해 주셨네요", "score": 96},
        {"comment": "다음 영상도 기대하겠습니다", "score": 95},
    ]
    styles = {x["comment"]: ("casual_imperfect" if i < 2 else "standard") for i,x in enumerate(rows)}
    standard = _select_diverse_results(rows, 3, {"id": "polite_viewer"}, styles)
    assert all(styles[x["comment"]] == "standard" for x in standard)
    sparse = _select_diverse_results(rows[:2], 2, None, styles)
    assert len(sparse) == 2
