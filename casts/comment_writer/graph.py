"""Comment Writer 그래프 엔트리포인트.

현재는 컨텍스트 수집 단계까지만 연결되어 있다. 다음 단계에서
생성 → 안전 필터 → 점수화 → 재생성 루프 → 승인 게이트 → 게시 노드를 잇는다.

Official document URL:
    - Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
"""

from langgraph.graph import END, START, StateGraph

from casts.base_graph import BaseGraph
from casts.comment_writer.modules.nodes import ContextNode
from casts.comment_writer.modules.state import InputState, OutputState, State


class CommentWriterGraph(BaseGraph):
    """Comment Writer Cast 의 그래프 정의.

    Attributes:
        input: 외부 입력 스키마.
        output: 외부 출력 스키마.
        state: 내부 공유 상태 스키마.
    """

    def __init__(self) -> None:
        super().__init__()
        self.input = InputState
        self.output = OutputState
        self.state = State

    def build(self):
        """그래프를 구성하고 컴파일한다.

        Returns:
            CompiledStateGraph: 실행 가능한 컴파일된 그래프.
        """
        builder = StateGraph(
            self.state, input_schema=self.input, output_schema=self.output
        )

        # 노드는 반드시 인스턴스로 등록한다 (클래스 객체가 아니라 dict 업데이트를 반환하도록).
        builder.add_node("ContextNode", ContextNode())
        builder.add_edge(START, "ContextNode")
        builder.add_edge("ContextNode", END)

        graph = builder.compile()
        graph.name = self.name
        return graph


comment_writer_graph = CommentWriterGraph()
