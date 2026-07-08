from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    post_text: str = Field(..., example="AI 시대에 개발자는 어떻게 살아남아야 할까?")
    comments: list[str] = Field(
        ...,
        example=[
            "결국 문제를 정의하는 능력이 중요해질 것 같아요.",
            "좋은 글 감사합니다.",
        ],
    )


class RecommendRequest(BaseModel):
    post_text: str = Field(..., example="AI 시대에 개발자는 어떻게 살아남아야 할까?")
    top_k: int = Field(default=5, ge=1, le=10)