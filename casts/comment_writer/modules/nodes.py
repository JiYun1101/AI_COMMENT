"""LangGraph nodes wired to the existing deterministic context + LLM/safety/ranker pipeline."""
from __future__ import annotations

from typing import Any
from casts.base_node import BaseNode
from casts.comment_writer.modules.tools import collect_video_context
from src.recommender.ranker import recommend_comments_with_meta
from src.recommender.persona import resolve_persona


class ContextNode(BaseNode):
    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        url = str(state.get("video_url") or "").strip()
        if not url:
            raise ValueError("video_url is required")
        return collect_video_context(
            url,
            additional_context=state.get("additional_context"),
            category_hint=state.get("category_hint"),
        )


class RecommendNode(BaseNode):
    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        top_k = int(state.get("top_k") or 5)
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be 1..10")
        ranked = recommend_comments_with_meta(
            state["post_text"],
            generation_context=state["generation_context"],
            top_k=top_k,
            persona=resolve_persona(state.get("persona_id", "none")),
        )
        return {
            "recommendations": ranked["recommendations"],
            "trace": ranked["trace"],
            "context_summary": state["context_summary"],
        }
