from typing import Literal

from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    post_text: str = Field(
        ...,
        min_length=1,
        json_schema_extra={"example": "AI 시대에 개발자는 어떻게 살아남아야 할까?"},
    )
    comments: list[str] = Field(
        ...,
        min_length=1,
        json_schema_extra={"example": [
            "결국 문제를 정의하는 능력이 중요해질 것 같아요.",
            "좋은 글 감사합니다.",
        ]},
    )


class CustomPersonaRequest(BaseModel):
    """Untrusted, browser-authored writing preferences: bounded and style-only."""
    id: str = Field(pattern=r"^custom_[A-Za-z0-9-]{8,64}$", max_length=71)
    name: str = Field(min_length=1, max_length=40)
    speech_style: str = Field(default="", max_length=240)
    recurring_phrases: list[str] = Field(default_factory=list, max_length=8)
    prohibited_phrases: list[str] = Field(default_factory=list, max_length=8)
    forbidden_marks: list[Literal[
        "period", "exclamation", "question", "comma", "tilde", "emoji", "laughter"
    ]] = Field(default_factory=list, max_length=7)
    sample_comment: str = Field(default="", max_length=200)


class RecommendRequest(BaseModel):
    post_text: str | None = Field(
        default=None,
        max_length=10_000,
        json_schema_extra={"example": "AI 시대에 개발자는 어떻게 살아남아야 할까?"},
    )
    youtube_url: str | None = Field(
        default=None,
        max_length=500,
        json_schema_extra={"example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    additional_context: str | None = Field(
        default=None,
        max_length=4_000,
        description="URL metadata/captions에 추가할 사용자 제공 맥락",
    )
    category: str | None = Field(
        default=None,
        max_length=80,
        description="하위 호환용 선택 힌트. 공식/파생 분류는 서버의 deterministic context builder가 결정합니다.",
    )
    persona_id: str = Field(
        default="none", max_length=71,
        description="기존 페르소나 ID 또는 custom_ 사용자 페르소나 ID",
    )
    custom_persona: CustomPersonaRequest | None = Field(
        default=None, description="custom_ 페르소나인 경우에만 함께 전송하는 말투 제한",
    )
    top_k: int = Field(default=5, ge=1, le=10)


class FeedbackRequest(BaseModel):
    useful: bool


class YouTubeCommentPublishRequest(BaseModel):
    video_id: str = Field(..., min_length=11, max_length=11)
    channel_id: str = Field(..., min_length=1, max_length=100)
    comment: str = Field(..., min_length=1, max_length=10_000)
    recommendation_id: str | None = Field(
        default=None,
        max_length=40,
        description="추천 결과에서 게시한 경우 그 추천 ID. 예측 점수와 실제 반응을 연결해 성과를 추적합니다.",
    )


class ReplyDraftRequest(BaseModel):
    comment: str = Field(..., min_length=1, max_length=2_000)
    category: Literal["question", "complaint", "risk", "praise", "other"] = "other"
    video_title: str | None = Field(default=None, max_length=300)


class CreatorReplyRequest(BaseModel):
    parent_id: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=2_000)
