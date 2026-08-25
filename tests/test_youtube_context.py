import pytest

from src.youtube.context import (
    InvalidYouTubeUrlError,
    build_reference_text,
    extract_video_id,
    fetch_youtube_context,
    parse_duration_seconds,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=42", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id(url, expected):
    assert extract_video_id(url) == expected


def test_extract_video_id_rejects_non_youtube_and_playlist_url():
    with pytest.raises(InvalidYouTubeUrlError):
        extract_video_id("https://example.com/watch?v=dQw4w9WgXcQ")
    with pytest.raises(InvalidYouTubeUrlError):
        extract_video_id("https://www.youtube.com/playlist?list=PL123")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("PT14M22S", 862), ("PT1H2M3S", 3723), ("PT45S", 45), (None, None), ("bad", None)],
)
def test_parse_duration_seconds(value, expected):
    assert parse_duration_seconds(value) == expected


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        if url.endswith("/videos"):
            return FakeResponse({"items": [{
                "snippet": {
                    "title": "테스트 영상", "description": "영상 설명입니다.",
                    "channelTitle": "테스트 채널", "channelId": "channel-1",
                    "publishedAt": "2026-08-24T00:00:00Z",
                    "thumbnails": {"high": {"url": "https://img.example/high.jpg"}},
                },
                "statistics": {"viewCount": "12345"},
                "contentDetails": {"duration": "PT14M22S"},
            }]})
        if url.endswith("/channels"):
            return FakeResponse({"items": [{"statistics": {
                "subscriberCount": "382000", "hiddenSubscriberCount": False
            }}]})
        raise AssertionError(url)


def test_fetch_context_and_reference_without_external_transcript_for_test_session():
    session = FakeSession()
    context = fetch_youtube_context(
        "https://youtu.be/dQw4w9WgXcQ", api_key="test-key", session=session
    )
    assert context.title == "테스트 영상"
    assert context.transcript_available is False
    assert len(session.calls) == 2
    reference = build_reference_text(context)
    assert "제목: 테스트 영상" in reference
    assert "설명: 영상 설명입니다." in reference


def test_injected_transcript_is_added_to_reference():
    session = FakeSession()
    context = fetch_youtube_context(
        "https://youtu.be/dQw4w9WgXcQ",
        api_key="test-key",
        session=session,
        transcript_fetcher=lambda _: ("공개 자막 내용입니다", "ko"),
    )
    assert context.transcript_available is True
    assert context.to_dict()["transcript_available"] is True
    assert "transcript" not in context.to_dict()
    assert "자막: 공개 자막 내용입니다" in build_reference_text(context)
