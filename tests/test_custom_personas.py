import pytest
from pydantic import ValidationError

from src.api.schemas import RecommendRequest
from src.llm.openai_client import build_generation_input, SYSTEM_INSTRUCTIONS
from src.recommender.persona import build_custom_persona, custom_persona_violation


CUSTOM = {
    "id": "custom_12345678",
    "name": "담백한 댓글러",
    "speech_style": "짧은 반말과 '~임' 같은 간결한 끝맺음",
    "recurring_phrases": ["갠적으로", "이 부분 괜찮음"],
    "prohibited_phrases": ["레전드"],
    "forbidden_marks": ["exclamation", "question", "laughter", "emoji"],
    "sample_comment": "이 부분은 좀 신기한듯",
}


def test_custom_persona_schema_and_matching_payload():
    parsed = RecommendRequest.model_validate({
        "post_text": "영상 설명", "persona_id": CUSTOM["id"],
        "custom_persona": CUSTOM,
    })
    assert parsed.custom_persona.name == "담백한 댓글러"
    for malformed in (
        {**CUSTOM, "id": "polite_viewer"},
        {**CUSTOM, "recurring_phrases": ["test"] * 9},
        {**CUSTOM, "forbidden_marks": ["delete_all"]},
    ):
        with pytest.raises(ValidationError):
            RecommendRequest.model_validate({
                "post_text": "영상 설명", "persona_id": CUSTOM["id"],
                "custom_persona": malformed,
            })


def test_user_authored_style_is_not_server_defined_trusted_persona():
    persona = build_custom_persona(CUSTOM)
    generation = build_generation_input(
        {"historical_comments": {}}, candidate_count=10, persona=persona,
    )
    task = generation["task"]
    assert "user_persona" in task
    assert "trusted_persona" not in task
    assert task["user_persona"]["speech_style"] == CUSTOM["speech_style"]
    assert "untrusted user-authored STYLE DATA" in SYSTEM_INSTRUCTIONS


def test_forbidden_words_and_punctuation_enforced_after_generation():
    persona = build_custom_persona(CUSTOM)
    assert custom_persona_violation("이거 레전드임", persona) is not None
    assert custom_persona_violation("이 부분 괜찮음!", persona) is not None
    assert custom_persona_violation("왜 이렇게 됐지?", persona) is not None
    assert custom_persona_violation("이 장면 너무 좋아ㅋㅋ", persona) is not None
    assert custom_persona_violation("이 내용은 생각보다 알차네", persona) is None
    assert custom_persona_violation("레전드!", None) is None


def test_custom_persona_cannot_use_oversized_or_empty_phrases():
    with pytest.raises(ValueError):
        build_custom_persona({**CUSTOM, "prohibited_phrases": ["x" * 61]})
    with pytest.raises(ValueError):
        build_custom_persona({**CUSTOM, "recurring_phrases": [" "]})
