import re

from src.llm.openai_client import validate_candidates
from src.recommender.ranker import recommend_comments_with_meta
from src.recommender.writing_style import clean_comment
from src.recommender.persona import PERSONAS


def test_clean_comment_removes_emojis_and_laughter_for_every_comment():
    before = [
        "이 장면 진짜 좋음ㅋㅋㅋㅋ 😄💜",
        "너무 재밌네요ㅎㅎ ㅠㅠ",
        "뭔가 새롭네요 ^_^",
        "이거 왜케 웃김 :D",
        "생각해보니 그렇네 lol",
        "이런 연출은 처음 봄 <3",
        "짧게 정리한게 좋네ㅋㅋ",
    ]
    after = [
        "이 장면 진짜 좋음", "너무 재밌네요", "뭔가 새롭네요",
        "이거 왜케 웃김", "생각해보니 그렇네", "이런 연출은 처음 봄",
        "짧게 정리한게 좋네",
    ]
    assert [clean_comment(text) for text in before] == after
    assert clean_comment("이건 어떻게 이해하면 될까요?") == "이건 어떻게 이해하면 될까요?"
    assert clean_comment("단가는 3.5만원이고 설정은 v1.2") == "단가는 3.5만원이고 설정은 v1.2"


def test_personas_all_forbid_emojis_even_playful():
    for persona in PERSONAS.values():
        assert persona["markers"] == "없음"
        rules = " ".join(persona["rules"]).lower()
        assert "ㅋㅋ" in rules
        assert ("do not use" in rules or "never use" in rules)


def test_model_validation_removes_markers_before_duplicate_check():
    result = validate_candidates({
        "candidates": [
            {"type": "casual", "comment": "먼가 신기하네ㅋㅋ😄", "writing_style": "casual_imperfect"},
            {"type": "casual", "comment": "먼가 신기하네ㅎㅎ💜", "writing_style": "casual_imperfect"},
            {"type": "question", "comment": "가격이 어떻게 될까요? :)"},
        ]
    }, minimum_count=2)
    assert [entry["comment"] for entry in result] == [
        "먼가 신기하네", "가격이 어떻게 될까요?",
    ]


def test_ranker_cleans_mock_clients_even_for_playful_personas(monkeypatch):
    rows = [
        ("왜케 이런 구도 낯설지 ㅋㅋ😄", "casual_imperfect"),
        ("갠적으로 구도가 재밌음ㅎㅎ", "casual_imperfect"),
        ("이번 영상의 설명이 구체적이라 이해하기 편했어요 ☺️", "standard"),
        ("이 주제를 더 깊게 다뤄 주실 수 있을까요? :)", "standard"),
        ("도입부 음악과 편집이 잘 맞는 것 같네요 💜", "standard"),
        ("이번 장면은 이상하게 기억에 남네요 ㅋㅋ", "standard"),
        ("영상 보면서 실제 활용 방법이 궁금해졌어요", "standard"),
    ]
    candidates = [{"comment": content, "writing_style": style, "type": "general"} for content, style in rows]
    monkeypatch.setattr("src.recommender.ranker.generate_candidates", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(
        "src.recommender.ranker.score_comments",
        lambda post_text, comments: [
            {"comment": comment, "score": 100 - i} for i, comment in enumerate(comments)
        ],
    )
    for persona in (None, {"id": "playful_casual"}):
        result = recommend_comments_with_meta("영상", generation_context={}, top_k=5, persona=persona)
        assert len(result["recommendations"]) == 5
        assert all(
            item["comment"] == clean_comment(item["comment"])
            and not re.search(r"ㅋ|ㅎ{2,}|[\U0001F300-\U0001FAFF]", item["comment"])
            for item in result["recommendations"]
        )
        assert result["trace"]["candidates"][0]["comment"] == "왜케 이런 구도 낯설지"
        assert result["recommendations"][0]["predicted_score"] == 100
        assert sum(
            entry["writing_style"] == "casual_imperfect" and entry["selected"]
            for entry in result["trace"]["candidates"]
        ) == 2
