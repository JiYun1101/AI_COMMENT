"""[Optional] Comment Writer 그래프의 프롬프트.

프롬프트 본문은 ``src/llm/prompting.py`` 한곳에서만 정의한다.
Cast 는 이를 재노출하고, 재생성 루프에서 쓸 피드백 문장만 조립한다.
(FastAPI 경로와 LangGraph 경로가 다른 프롬프트를 쓰면 두 결과를 비교할 수
없게 되므로 의도적으로 이 모듈에는 프롬프트 문자열을 두지 않는다.)

Official document URL:
    - Messages: https://docs.langchain.com/oss/python/langchain/messages
"""

from __future__ import annotations

from src.llm.prompting import SYSTEM_INSTRUCTIONS, TYPE_GUIDELINES, build_user_input

__all__ = [
    "SYSTEM_INSTRUCTIONS",
    "TYPE_GUIDELINES",
    "GENERATION_TYPES",
    "build_user_input",
    "build_revision_feedback",
]

# 유형별로 나눠 호출할 때 사용할 순서.
# 로컬 모델은 한 응답 안에서 유형 다양성이 빠르게 무너지므로 분리 호출이 기본이다.
GENERATION_TYPES = ("insight", "empathy", "question", "casual")


def build_revision_feedback(
    *,
    blocked: list[dict] | None = None,
    duplicate_count: int = 0,
    shortfall: int = 0,
) -> str:
    """재생성 시 모델에 되먹일 실패 사유를 한 문장으로 만든다.

    Args:
        blocked: 안전 필터에 걸린 후보들 (``reason`` 키 사용).
        duplicate_count: 중복으로 버려진 후보 수.
        shortfall: 목표 대비 부족한 후보 수.

    Returns:
        str: 피드백 문장. 되먹일 내용이 없으면 빈 문자열.
    """
    parts: list[str] = []

    reasons = sorted({str(item.get("reason")) for item in (blocked or []) if item.get("reason")})
    if reasons:
        parts.append(f"Previous attempt had candidates blocked by the safety filter ({', '.join(reasons)}).")
    if duplicate_count:
        parts.append(f"{duplicate_count} candidates were discarded as duplicates.")
    if shortfall > 0:
        parts.append(f"{shortfall} more usable candidates are needed.")

    return " ".join(parts)
