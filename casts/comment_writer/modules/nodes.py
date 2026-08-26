"""[Required] Comment Writer 그래프의 노드 구현.

현재 단계에서는 컨텍스트 수집 노드만 구현되어 있다.
생성 · 안전 필터 · 점수화 · 재생성 루프 노드는 다음 단계에서 추가한다.

Official document URL:
    - Nodes: https://docs.langchain.com/oss/python/langgraph/graph-api#nodes
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from casts.base_node import BaseNode
from casts.comment_writer.modules.tools import collect_video_context


class ContextNode(BaseNode):
    """유튜브 영상 컨텍스트를 수집해 이후 노드가 쓸 입력을 준비한다.

    LLM 을 쓰지 않는 결정적 노드다. 여기서 만든 ``post_text`` 가 랭킹 모델의
    임베딩 유사도 기준이 되므로, 학습 데이터와 같은 방식으로 구성해야 한다.
    """

    def __init__(self, verbose: bool = False) -> None:
        super().__init__(verbose=verbose)

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """영상 URL 로부터 컨텍스트를 수집한다.

        Args:
            state: 현재 그래프 상태. ``video_url`` 이 필요하다.

        Returns:
            dict: ``video_id`` · ``post_text`` · ``generation_context`` ·
            ``context_summary`` 상태 업데이트.
        """
        video_url = str(state.get("video_url") or "").strip()
        if not video_url:
            raise ValueError("video_url 이 필요합니다.")

        collected = collect_video_context(
            video_url,
            additional_context=state.get("additional_context"),
            category_hint=state.get("category_hint"),
        )
        self.log("context collected", video_id=collected["video_id"])

        summary = collected["context_summary"]
        return {
            "video_id": collected["video_id"],
            "post_text": collected["post_text"],
            "generation_context": collected["generation_context"],
            "context_summary": summary,
            "revision_count": 0,
            "messages": [
                AIMessage(
                    content=f"영상 컨텍스트 수집 완료: {collected['video_id']} "
                    f"(category={summary.get('primary_category')})"
                )
            ],
        }
