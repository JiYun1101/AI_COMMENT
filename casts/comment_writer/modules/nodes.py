"""LangGraph nodes wired to the existing deterministic context + LLM/safety/ranker pipeline."""
from __future__ import annotations

from typing import Any
from casts.base_node import BaseNode
from casts.comment_writer.modules.tools import collect_video_context
from src.recommender.ranker import recommend_comments_with_meta
from src.llm.openai_client import OpenAIResponsesClient, LLMNotReadyError
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
            youtube_api_key=state.get("youtube_api_key") or None,
        )


class RecommendNode(BaseNode):
    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        top_k = int(state.get("top_k") or 5)
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be 1..10")
        override_key = state.get("openai_api_key") or None
        override_model = state.get("openai_model") or None
        client = None
        if override_key:
            if not override_model:
                raise LLMNotReadyError("OpenAI model must accompany a per-request API key")
            client = OpenAIResponsesClient(api_key=override_key, model=override_model)
        ranked = recommend_comments_with_meta(
            state["post_text"],
            generation_context=state["generation_context"],
            top_k=top_k,
            persona=resolve_persona(state.get("persona_id", "none")),
            generation_client=client,
        )
        return {
            "recommendations": ranked["recommendations"],
            "trace": ranked["trace"],
            "context_summary": state["context_summary"],
        }
