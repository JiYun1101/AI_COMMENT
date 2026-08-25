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


def test_extract_video_id_rejects_non_youtube_url():
    with pytest.raises(InvalidYouTubeUrlError):
        extract_video_id("https://example.com/watch?v=dQw4w9WgXcQ")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("PT14M22S", 862),
        ("PT1H2M3S", 3723),
        ("PT45S", 45),
        (None, None),
        ("not-a-duration", None),
    ],
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
            return FakeResponse(
                {
                    "items": [
                        {
                            "snippet": {
                                "title": "테스트 영상",
                                "description": "영상 설명입니다.",
                                "channelTitle": "테스트 채널",
                                "channelId": "channel-1",
                                "publishedAt": "2026-08-24T00:00:00Z",
                                "thumbnails": {
                                    "high": {"url": "https://img.example/high.jpg"}
                                },
                            },
                            "statistics": {"viewCount": "12345"},
                            "contentDetails": {"duration": "PT14M22S"},
                        }
                    ]
                }
            )
        if url.endswith("/channels"):
            return FakeResponse(
                {
                    "items": [
                        {
                            "statistics": {
                                "subscriberCount": "382000",
                                "hiddenSubscriberCount": False,
                            }
                        }
                    ]
                }
            )
        raise AssertionError(f"unexpected URL: {url}")


def test_fetch_youtube_context_and_reference_text():
    session = FakeSession()

    context = fetch_youtube_context(
        "https://youtu.be/dQw4w9WgXcQ",
        api_key="test-key",
        session=session,
    )

    assert context.video_id == "dQw4w9WgXcQ"
    assert context.title == "테스트 영상"
    assert context.description == "영상 설명입니다."
    assert context.channel == "테스트 채널"
    assert context.subscriber_count == 382000
    assert context.view_count == 12345
    assert context.duration_seconds == 862
    assert context.thumbnail_url == "https://img.example/high.jpg"
    assert len(session.calls) == 2

    reference_text = build_reference_text(context)
    assert "제목: 테스트 영상" in reference_text
    assert "채널: 테스트 채널" in reference_text
    assert "설명: 영상 설명입니다." in reference_text
