"""[Optional] Comment Writer 그래프가 쓰는 도구.

이 모듈은 **얇은 어댑터**다. 실제 로직은 전부 ``src/`` 의 도메인 계층에 있고,
여기서는 그래프가 쓰기 좋은 형태로 감싸기만 한다. 의존 방향은 언제나
``casts/ → src/`` 한쪽이며, ``src/`` 는 LangGraph 를 알지 못한다.

각 기능은 두 형태로 제공된다.

* ``*_fn`` 없는 일반 함수: 노드가 직접 호출한다 (도구 호출 오버헤드 없음).
* ``@tool`` 이 붙은 객체: 에이전트/미들웨어가 가로챌 수 있는 형태.

Official document URL:
    - Tools: https://docs.langchain.com/oss/python/langchain/tools
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from casts.comment_writer.modules.models import get_comment_generation_client
from src.model.predict import score_comments
from src.recommender.generation_context import (
    build_generation_context,
    summarize_generation_context,
)
from src.recommender.safety_filter import get_block_reason
from src.youtube.context import build_reference_text, fetch_youtube_context


def collect_video_context(
    video_url: str,
    *,
    additional_context: str | None = None,
    category_hint: str | None = None,
) -> dict[str, Any]:
    """유튜브 영상 컨텍스트를 수집하고 생성/랭킹용 입력을 구성한다.

    ``post_text`` 는 랭킹 모델이 임베딩 유사도(``post_comment_sim``)를 계산할 때
    쓰는 기준 텍스트다. 학습 데이터와 같은 방식으로 구성해야 하므로
    ``build_reference_text`` 결과를 그대로 쓰고, 사용자 추가 맥락만 뒤에 붙인다.

    Args:
        video_url: 유튜브 영상 URL.
        additional_context: 사용자가 덧붙이는 맥락.
        category_hint: 카테고리 힌트.

    Returns:
        dict: ``video_id`` · ``post_text`` · ``generation_context`` ·
        ``context_summary`` · ``youtube_context`` 를 담은 딕셔너리.
    """
    youtube_context = fetch_youtube_context(video_url)
    reference_text = build_reference_text(youtube_context)

    extra = (additional_context or "").strip() or None
    post_text = f"{reference_text}\n\n추가 맥락: {extra}" if extra else reference_text

    generation_context = build_generation_context(
        reference_text,
        youtube_context=youtube_context,
        additional_context=extra,
        category_hint=category_hint,
    )

    return {
        "video_id": youtube_context.video_id,
        "post_text": post_text,
        "generation_context": generation_context,
        "context_summary": summarize_generation_context(generation_context),
        "youtube_context": youtube_context.to_dict(),
    }


def generate_comment_candidates(
    generation_context: dict,
    *,
    candidate_count: int,
    comment_type: str | None = None,
    feedback: str | None = None,
    client: Any | None = None,
) -> list[dict]:
    """설정된 LLM 으로 댓글 후보를 생성한다.

    Args:
        generation_context: ``collect_video_context`` 가 만든 결정적 컨텍스트.
        candidate_count: 요청할 후보 수.
        comment_type: 특정 유형만 생성할 때의 유형명.
        feedback: 재생성 시 되먹일 실패 사유.
        client: 테스트에서 주입할 클라이언트. 생략하면 팩토리가 만든다.

    Returns:
        list[dict]: ``{"type": ..., "comment": ...}`` 후보 목록.
    """
    provider = client or get_comment_generation_client()
    return provider.generate(
        generation_context,
        candidate_count=candidate_count,
        comment_type=comment_type,
        feedback=feedback,
    )


def check_comment_safety(comment: str) -> dict[str, Any]:
    """댓글 하나를 규칙 기반 안전 필터에 통과시킨다.

    LLM 이 아니라 결정적 규칙이므로 결과가 재현 가능하고 테스트할 수 있다.

    Returns:
        dict: ``{"safe": bool, "reason": str | None}``.
    """
    reason = get_block_reason(comment)
    return {"safe": reason is None, "reason": reason}


def score_comment_candidates(post_text: str, comments: list[str]) -> list[dict]:
    """학습된 반응 예측 모델로 댓글 후보를 점수화한다 (점수 내림차순).

    Args:
        post_text: ``collect_video_context`` 가 만든 기준 텍스트.
        comments: 점수를 매길 댓글 문자열 목록.

    Returns:
        list[dict]: ``{"comment": ..., "score": ...}`` 목록.
    """
    return score_comments(post_text=post_text, comments=comments)


# --- 에이전트/미들웨어가 가로챌 수 있는 도구 형태 -----------------------------

@tool("collect_video_context")
def collect_video_context_tool(video_url: str) -> dict:
    """Collect deterministic YouTube video context for a given video URL."""
    return collect_video_context(video_url)


@tool("check_comment_safety")
def check_comment_safety_tool(comment: str) -> dict:
    """Check one comment against the rule-based safety filter."""
    return check_comment_safety(comment)


@tool("score_comment_candidates")
def score_comment_candidates_tool(post_text: str, comments: list[str]) -> list[dict]:
    """Score comment candidates with the trained reaction-prediction model."""
    return score_comment_candidates(post_text, comments)


COMMENT_WRITER_TOOLS = [
    collect_video_context_tool,
    check_comment_safety_tool,
    score_comment_candidates_tool,
]
