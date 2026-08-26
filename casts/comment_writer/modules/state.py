"""[Required] Comment Writer 그래프의 상태 정의.

세 가지 상태를 분리한다.

* ``InputState``  : 외부 호출자가 넣는 값 (영상 URL 등)
* ``OutputState`` : 외부로 돌려주는 값 (추천 결과와 추적 정보)
* ``State``       : 노드들이 공유하는 내부 작업 상태

``candidates`` / ``blocked`` 는 재생성 루프에서 시도마다 누적되어야 하므로
``operator.add`` 리듀서를 붙인다. 나머지는 마지막 노드의 값으로 덮어쓴다.

Official document URL:
    - State: https://docs.langchain.com/oss/python/langgraph/graph-api#state
"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from langgraph.graph import MessagesState
from typing_extensions import NotRequired, TypedDict


class InputState(TypedDict):
    """그래프 입력.

    Attributes:
        video_url: 댓글을 달 유튜브 영상 URL.
        top_k: 최종적으로 돌려줄 추천 댓글 수.
        additional_context: 사용자가 덧붙이는 맥락(선택).
        category_hint: 카테고리 힌트(선택).
    """

    video_url: str
    top_k: NotRequired[int]
    additional_context: NotRequired[str]
    category_hint: NotRequired[str]


class OutputState(TypedDict):
    """그래프 출력.

    Attributes:
        recommendations: 점수순으로 정렬된 추천 댓글.
        trace: 후보별 안전 필터·랭커 결과 추적 정보.
        context_summary: 결정적으로 수집·분류된 영상 컨텍스트 요약.
    """

    recommendations: list[dict]
    trace: dict
    context_summary: dict


class State(MessagesState):
    """노드 간 공유 상태.

    Attributes:
        video_url: 입력 영상 URL.
        top_k: 요청된 추천 수.
        additional_context: 사용자가 덧붙인 맥락.
        category_hint: 카테고리 힌트.
        video_id: 추출된 11자리 영상 ID.
        post_text: 랭킹 모델에 넣는 기준 텍스트(제목·설명·자막 등을 합친 값).
        generation_context: LLM 생성에 넘기는 결정적 컨텍스트.
        context_summary: 컨텍스트 요약(출력용).
        candidates: 생성된 후보 누적.
        blocked: 안전 필터에 걸린 후보 누적.
        scored: 반응 예측 점수가 매겨진 후보.
        recommendations: 최종 추천 결과.
        trace: 후보 추적 정보.
        revision_count: 재생성 시도 횟수.
        feedback: 다음 생성에 되먹일 실패 사유.
        error: 사용자에게 보여줄 실패 메시지.
    """

    # messages 는 MessagesState 에서 상속받는다 (add_messages 리듀서).
    video_url: str
    top_k: int
    additional_context: str
    category_hint: str

    video_id: str
    post_text: str
    generation_context: dict[str, Any]
    context_summary: dict[str, Any]

    candidates: Annotated[list[dict], operator.add]
    blocked: Annotated[list[dict], operator.add]
    scored: list[dict]
    recommendations: list[dict]
    trace: dict[str, Any]

    revision_count: int
    feedback: str
    error: str
