from fastapi.testclient import TestClient

from src.api.main import app
from src.youtube.video_moments import get_video_caption_moments, group_caption_moments

VIDEO = "dQw4w9WgXcQ"


def test_time_aligned_captions_no_imagined_video_frames():
    frames = [
        {"start": 0, "duration": 3, "text": "처음 인사"},
        {"start": 19, "duration": 4, "text": "  두 번째  장면 언급 "},
        {"start": 73, "duration": 6, "text": "다음 주제"},
    ]
    result = get_video_caption_moments(VIDEO, fetcher=lambda vid: (frames, "ko"))
    assert result["video_id"] == VIDEO
    assert result["status"] == "available"
    assert result["frames_analyzed"] is False
    assert result["evidence"] == "captions_only"
    assert [m["start_seconds"] for m in result["moments"]] == [0, 60]
    assert result["moments"][0]["text"] == "처음 인사 두 번째 장면 언급"


def test_evenly_samples_windows_from_whole_video():
    captions = [{"start": i * 60, "text": f"minute {i}"} for i in range(35)]
    moments = group_caption_moments(captions)
    assert len(moments) == 12
    assert moments[0]["start_seconds"] == 0
    assert moments[-1]["start_seconds"] == 34 * 60
    assert all(x["source"] == "captions" for x in moments)


def test_fetch_failure_returns_empty_evidence_not_fabricated_scenes():
    def fail(_):
        raise RuntimeError("transcript service unavailable")
    value = get_video_caption_moments(VIDEO, fetcher=fail)
    assert value["status"] == "fetch_failed"
    assert value["moments"] == []
    assert value["frames_analyzed"] is False


def test_video_moments_endpoint_requires_server_auth(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "test-owner")
    client = TestClient(app)
    url = f"/videos/moments?url=https://www.youtube.com/watch?v={VIDEO}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-API-Key": "test-owner"},
                      params={"url": "https://evil.example/video"}).status_code == 422
