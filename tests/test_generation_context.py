from datetime import datetime, timezone

from src.recommender.generation_context import build_generation_context, summarize_generation_context
from src.youtube.context import YouTubeVideoContext


def _no_history(monkeypatch):
    monkeypatch.setattr(
        "src.recommender.generation_context.build_historical_profile",
        lambda *args, **kwargs: {"coverage": "none", "matched_count": 0, "reference_examples": []},
    )


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
    _no_history(monkeypatch)
    context = build_generation_context("제주 여행 브이로그 맛집 후기")
    assert context["source"]["type"] == "manual"
    assert context["youtube"]["category_id"] is None
    assert context["format"]["kind"] == "unknown"
    assert "travel" in context["content"]["topics"]
    assert "vlog" in context["content"]["content_styles"]
    assert context["primary_category"] == "travel"


def test_legacy_category_hint_is_recorded_but_cannot_override_primary_category(monkeypatch):
    _no_history(monkeypatch)
    context = build_generation_context(
        "제주 여행 브이로그 맛집 후기",
        category_hint="arbitrary-client-category",
    )
    assert context["source"]["legacy_category_hint"] == "arbitrary-client-category"
    assert context["primary_category"] == "travel"
    assert "arbitrary-client-category" not in context["content"]["topics"]

    vlog_hint = build_generation_context("제주 여행 맛집 후기", category_hint="vlog")
    assert vlog_hint["source"]["legacy_category_hint"] == "vlog"
    assert vlog_hint["primary_category"] == "travel"
    assert "vlog" in vlog_hint["content"]["content_styles"]


def test_audience_orientation_is_content_level_heuristic(monkeypatch):
    _no_history(monkeypatch)
    context = build_generation_context("20대 여성 출근 코디와 여자 직장인 패션 추천")
    assert "young_adult" in context["audience"]["target_age"]
    assert context["audience"]["orientation"] == "female_oriented"
    assert context["audience"]["basis"] == "official_flags_plus_explicit_content_heuristics"


def test_short_ascii_topic_keywords_do_not_match_inside_longer_words(monkeypatch):
    _no_history(monkeypatch)
    context = build_generation_context("Chair design details and interior styling")
    assert "ai" not in context["content"]["topics"]
    assert "autos" not in context["content"]["topics"]


def test_standalone_ascii_topic_keyword_still_matches(monkeypatch):
    _no_history(monkeypatch)
    context = build_generation_context("AI tools for software teams")
    assert "ai" in context["content"]["topics"]
    assert "software" in context["content"]["topics"]


def test_woman_does_not_also_match_man_orientation(monkeypatch):
    _no_history(monkeypatch)
    context = build_generation_context("Women fashion guide for a woman starting a new job")
    assert context["audience"]["orientation"] == "female_oriented"


def test_youtube_topic_details_feed_derived_topic_classifier(monkeypatch):
    _no_history(monkeypatch)
    youtube = YouTubeVideoContext(
        video_id="topicVideo01",
        url="https://www.youtube.com/watch?v=topicVideo01",
        title="새로운 무대",
        description="오늘 공개된 영상입니다.",
        channel="채널",
        subscriber_count=1_000,
        view_count=5_000,
        published_at="2026-08-26T00:00:00Z",
        duration_seconds=240,
        thumbnail_url=None,
        category_id="10",
        category_name="Music",
        topic_categories=("https://en.wikipedia.org/wiki/Music",),
    )
    context = build_generation_context(
        "제목: 새로운 무대\n설명: 오늘 공개된 영상입니다.",
        youtube_context=youtube,
        now=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc),
    )
    assert context["primary_category"] == "Music"
    assert "music" in context["content"]["topics"]
