"""Comment Writer Cast 의 상태/도구/모델 팩토리 테스트.

LLM · 유튜브 API · 학습된 모델은 모두 대역으로 대체한다.
"""

import typing

import pytest

from casts.comment_writer.modules import tools
from casts.comment_writer.modules.models import (
    comment_generation_readiness,
    get_comment_generation_client,
    resolve_provider,
)
from casts.comment_writer.modules.prompts import build_revision_feedback
from casts.comment_writer.modules.state import InputState, OutputState, State
from src.llm.base import LLMNotReadyError
from src.llm.ollama_client import OllamaCommentClient
from src.llm.openai_client import OpenAIResponsesClient
from src.youtube.context import YouTubeVideoContext


def _fake_video_context():
    return YouTubeVideoContext(
        video_id="abcdefghijk",
        url="https://www.youtube.com/watch?v=abcdefghijk",
        title="AI 시대 개발자의 생존 전략",
        description="AI 도구가 바꾸는 개발 업무를 정리했습니다.",
        channel="테크 채널",
        subscriber_count=12_000,
        view_count=53_000,
        published_at="2026-08-01T09:00:00Z",
        duration_seconds=720,
        thumbnail_url=None,
        category_name="Science & Technology",
        tags=("AI", "개발자"),
    )


class FakeClient:
    def __init__(self):
        self.calls = []

    def generate(self, context, *, candidate_count, comment_type=None, feedback=None):
        self.calls.append(
            {
                "candidate_count": candidate_count,
                "comment_type": comment_type,
                "feedback": feedback,
            }
        )
        return [{"type": comment_type or "general", "comment": "테스트 댓글입니다."}]


# --- state ------------------------------------------------------------------

def test_state_separates_input_output_and_internal_fields():
    # 외부 인터페이스에는 내부 작업 필드가 새어 나가면 안 된다.
    assert "video_url" in InputState.__annotations__
    assert "generation_context" not in InputState.__annotations__
    assert set(OutputState.__annotations__) == {"recommendations", "trace", "context_summary"}
    # 재생성 루프에서 시도별로 누적되어야 하는 필드에는 리듀서가 붙어 있어야 한다.
    hints = typing.get_type_hints(State, include_extras=True)
    for field in ("candidates", "blocked"):
        assert getattr(hints[field], "__metadata__", None), f"{field} 에 리듀서가 없습니다."
    assert not getattr(hints["scored"], "__metadata__", None)


# --- tools ------------------------------------------------------------------

def test_collect_video_context_builds_post_text_and_generation_context(monkeypatch):
    monkeypatch.setattr(tools, "fetch_youtube_context", lambda url: _fake_video_context())

    collected = tools.collect_video_context("https://youtu.be/abcdefghijk")

    assert collected["video_id"] == "abcdefghijk"
    # post_text 는 랭킹 모델의 임베딩 유사도 기준이므로 제목이 반드시 들어가야 한다.
    assert "AI 시대 개발자의 생존 전략" in collected["post_text"]
    assert collected["generation_context"]["source"]["type"] == "youtube"
    assert "primary_category" in collected["context_summary"]


def test_collect_video_context_appends_additional_context(monkeypatch):
    monkeypatch.setattr(tools, "fetch_youtube_context", lambda url: _fake_video_context())

    collected = tools.collect_video_context(
        "https://youtu.be/abcdefghijk",
        additional_context="주니어 개발자 관점으로",
    )

    assert "추가 맥락: 주니어 개발자 관점으로" in collected["post_text"]
    assert collected["generation_context"]["source"]["additional_context"] == "주니어 개발자 관점으로"


def test_check_comment_safety_uses_shared_rule_filter():
    assert tools.check_comment_safety("영상 잘 봤습니다. 정리가 깔끔하네요.")["safe"] is True

    blocked = tools.check_comment_safety("구독하고 좋아요 눌러주세요 http://spam.example.com")
    assert blocked["safe"] is False
    assert blocked["reason"]


def test_score_comment_candidates_delegates_to_trained_model(monkeypatch):
    captured = {}

    def fake_score(*, post_text, comments):
        captured["post_text"] = post_text
        captured["comments"] = comments
        return [{"comment": comments[0], "score": 88.0}]

    monkeypatch.setattr(tools, "score_comments", fake_score)

    result = tools.score_comment_candidates("영상 본문", ["댓글 하나"])

    assert result == [{"comment": "댓글 하나", "score": 88.0}]
    assert captured["post_text"] == "영상 본문"


def test_generate_comment_candidates_passes_type_and_feedback():
    client = FakeClient()

    result = tools.generate_comment_candidates(
        {"historical_comments": {}},
        candidate_count=4,
        comment_type="empathy",
        feedback="duplicates",
        client=client,
    )

    assert result[0]["type"] == "empathy"
    assert client.calls == [{"candidate_count": 4, "comment_type": "empathy", "feedback": "duplicates"}]


def test_tools_are_exposed_as_interceptable_tool_objects():
    # HITL 미들웨어가 가로챌 수 있으려면 도구 객체 형태여야 한다.
    assert [tool.name for tool in tools.COMMENT_WRITER_TOOLS] == [
        "collect_video_context",
        "check_comment_safety",
        "score_comment_candidates",
    ]


# --- models -----------------------------------------------------------------

def test_default_provider_is_local_ollama(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "exaone3.5:7.8b")
    assert resolve_provider() == "ollama"
    assert isinstance(get_comment_generation_client(), OllamaCommentClient)


def test_provider_can_be_switched_to_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    assert isinstance(get_comment_generation_client(), OpenAIResponsesClient)


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(LLMNotReadyError):
        get_comment_generation_client()


def test_readiness_reports_configured_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    readiness = comment_generation_readiness()
    assert readiness["provider"] == "ollama"
    assert readiness["ready"] is False


# --- prompts ----------------------------------------------------------------

def test_build_revision_feedback_summarises_failures():
    feedback = build_revision_feedback(
        blocked=[{"reason": "spam"}, {"reason": "spam"}, {"reason": "profanity"}],
        duplicate_count=2,
        shortfall=3,
    )
    assert "profanity, spam" in feedback
    assert "2 candidates were discarded as duplicates." in feedback
    assert "3 more usable candidates are needed." in feedback


def test_build_revision_feedback_is_empty_when_nothing_failed():
    assert build_revision_feedback() == ""


# --- graph / nodes ----------------------------------------------------------

def test_graph_compiles_with_context_node():
    from casts.comment_writer.graph import comment_writer_graph

    compiled = comment_writer_graph()
    assert "ContextNode" in compiled.get_graph().nodes


def test_context_node_returns_state_updates(monkeypatch):
    from casts.comment_writer.modules.nodes import ContextNode

    monkeypatch.setattr(tools, "fetch_youtube_context", lambda url: _fake_video_context())

    update = ContextNode().execute({"video_url": "https://youtu.be/abcdefghijk"})

    assert update["video_id"] == "abcdefghijk"
    assert update["post_text"]
    assert update["revision_count"] == 0


def test_context_node_requires_video_url():
    from casts.comment_writer.modules.nodes import ContextNode

    with pytest.raises(ValueError):
        ContextNode().execute({})
