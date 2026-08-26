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
    top_k: int = Field(default=5, ge=1, le=10)


class FeedbackRequest(BaseModel):
    useful: bool
