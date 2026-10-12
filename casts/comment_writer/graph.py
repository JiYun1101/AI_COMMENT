"""Executable LangGraph interface around the production comment recommender."""
from langgraph.graph import END, START, StateGraph
from casts.comment_writer.modules.state import State, InputState, OutputState
from casts.comment_writer.modules.nodes import ContextNode, RecommendNode


def build_comment_writer_graph():
    builder = StateGraph(State, input_schema=InputState, output_schema=OutputState)
    builder.add_node("ContextNode", ContextNode())
    builder.add_node("RecommendNode", RecommendNode())
    builder.add_edge(START, "ContextNode")
    builder.add_edge("ContextNode", "RecommendNode")
    builder.add_edge("RecommendNode", END)
    return builder.compile(name="CommentWriter")


# LangGraph service expects a compiled graph here, not a factory object.
comment_writer_graph = build_comment_writer_graph()
