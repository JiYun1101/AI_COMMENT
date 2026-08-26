from datetime import datetime, timezone

from src.recommender.generation_context import build_generation_context, summarize_generation_context
from src.youtube.context import YouTubeVideoContext


def test_youtube_generation_context_uses_official_and_derived_signals(monkeypatch):
    monkeypatch.setattr(
        "src.recommender.generation_context.build_historical_profile",
        lambda *args, **kwargs: {
            "coverage": "matched_legacy_category",
            "matched_count": 12,
            "reference_examples": ["좋은 참고 댓글입니다."],
        },
    )
    youtube = YouTubeVideoContext(
        video_id="dQw4w9WgXcQ",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="AI 개발자 커리어 인터뷰",
        description="신입 개발자와 AI 시대 커리어를 토론합니다.",
        channel="테크살롱",
        subscriber_count=100_000,
        view_count=200_000,
        published_at="2026-08-26T00:00:00Z",
        duration_seconds=1800,
        thumbnail_url=None,
        transcript="AI와 프론트엔드 개발자 취업 이야기를 나눕니다.",
        transcript_language="ko",
        category_id="28",
        category_name="Science & Technology",
        tags=("AI", "개발자", "커리어"),
        like_count=10_000,
        comment_count=1_000,
        made_for_kids=False,
        live_broadcast_content="none",
    )
    context = build_generation_context(
        "제목: AI 개발자 커리어 인터뷰\n설명: 신입 개발자와 AI 시대 커리어를 토론합니다.",
        youtube_context=youtube,
        now=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc),
    )

    assert context["primary_category"] == "Science & Technology"
    assert {"ai", "software", "career"} & set(context["content"]["topics"])
    assert context["format"]["kind"] == "long_form"
    assert context["temporal"]["freshness"] == "breaking"
    assert context["popularity"]["hype_basis"] == "single_snapshot_proxy"
    assert context["historical_comments"]["matched_count"] == 12
    summary = summarize_generation_context(context)
    assert summary["official_category"] == "Science & Technology"


def test_manual_context_does_not_invent_youtube_metadata(monkeypatch):
    monkeypatch.setattr(
        "src.recommender.generation_context.build_historical_profile",
        lambda *args, **kwargs: {"coverage": "none", "matched_count": 0, "reference_examples": []},
    )
    context = build_generation_context("제주 여행 브이로그 맛집 후기")
    assert context["source"]["type"] == "manual"
    assert context["youtube"]["category_id"] is None
    assert context["format"]["kind"] == "unknown"
    assert "travel" in context["content"]["topics"]
    assert "vlog" in context["content"]["content_styles"]


def test_audience_orientation_is_content_level_heuristic(monkeypatch):
    monkeypatch.setattr(
        "src.recommender.generation_context.build_historical_profile",
        lambda *args, **kwargs: {"coverage": "none", "matched_count": 0, "reference_examples": []},
    )
    context = build_generation_context("20대 여성 출근 코디와 여자 직장인 패션 추천")
    assert "young_adult" in context["audience"]["target_age"]
    assert context["audience"]["orientation"] == "female_oriented"
    assert context["audience"]["basis"] == "official_flags_plus_explicit_content_heuristics"
