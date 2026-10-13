from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.youtube import video_performance as source
from src.storage.video_store import (
    save_video_metrics, list_video_metrics, recently_synced,
)
from src.api.main import app

VIDEO1 = "dQw4w9WgXcQ"
VIDEO2 = "9bZkp7q19f0"
BASE = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)


def item(vid, owner="UC_OWN", views="123"):
    return {"id": vid,
            "snippet": {"title": "영상", "channelId": owner, "publishedAt": "2026-10-01T00:00:00Z",
                        "thumbnails": {"medium": {"url": "https://i.ytimg.com/thumb.jpg"}}},
            "status": {"privacyStatus": "public"},
            "statistics": {"viewCount": views, "likeCount": "12", "commentCount": "4"}}


def youtube_fake(calls):
    def fake(_http, url, *, params, **kwargs):
        calls.append((url, params))
        if url.endswith("/channels"):
            return {"items": [{"id": "UC_OWN", "snippet": {"title": "내 채널"},
                "contentDetails": {"relatedPlaylists": {"uploads": "UU_OWN"}}}]}
        if url.endswith("/playlistItems"):
            return {"items": [{"contentDetails": {"videoId": VIDEO1}},
                              {"contentDetails": {"videoId": VIDEO2}}]}
        if url.endswith("/videos"):
            video_ids = params["id"].split(",")
            records = {VIDEO1: item(VIDEO1), VIDEO2: item(VIDEO2, owner="UC_OTHER")}
            return {"items": [records[vid] for vid in video_ids if vid in records]}
        raise AssertionError("Unexpected YouTube URL " + url)
    return fake


def test_owned_youtube_uploads_and_owner_guard(monkeypatch):
    calls = []
    monkeypatch.setattr(source, "_authorized_json", youtube_fake(calls))
    result = source.fetch_my_videos(limit=100)
    assert result["channel_id"] == "UC_OWN"
    assert result["channel_title"] == "내 채널"
    assert [v["video_id"] for v in result["videos"]] == [VIDEO1]
    assert result["videos"][0]["views"] == 123
    assert [url.split("/")[-1] for url, _ in calls] == ["channels", "playlistItems", "videos"]
    assert calls[1][1]["playlistId"] == "UU_OWN"
    assert calls[2][1]["id"] == f"{VIDEO1},{VIDEO2}"


def test_older_foreign_video_refused(monkeypatch):
    calls = []
    monkeypatch.setattr(source, "_authorized_json", youtube_fake(calls))
    with pytest.raises(source.YouTubeCommentPublishError):
        source.fetch_owned_video(VIDEO2)
    assert source.fetch_owned_video(VIDEO1)["videos"][0]["video_id"] == VIDEO1


def test_null_counters_do_not_become_zero(monkeypatch):
    def fake(_http, url, *, params, **_kwargs):
        if url.endswith("/channels"):
            return {"items": [{"id": "UC_OWN", "contentDetails": {"relatedPlaylists": {"uploads": "UUL"}}}]}
        if url.endswith("/playlistItems"):
            return {"items": [{"contentDetails": {"videoId": VIDEO1}}]}
        return {"items": [{"id": VIDEO1, "snippet": {"channelId": "UC_OWN"}}]}
    monkeypatch.setattr(source, "_authorized_json", fake)
    assert source.fetch_my_videos()["videos"][0]["views"] is None
    assert source.fetch_my_videos()["videos"][0]["likes"] is None


def test_channel_isolation_snapshots_and_cooldown(tmp_path):
    path = tmp_path / "video.db"
    record = {"video_id": VIDEO1, "title": "Test", "published_at": BASE.isoformat(),
              "privacy_status": "public", "views": 100, "likes": 1, "comments": 0}
    save_video_metrics("UC_A", "A", [record], observed_at=BASE - timedelta(days=7), path=path)
    assert not recently_synced("UC_A", now=BASE, path=path)
    save_video_metrics("UC_A", "A", [{**record, "views": 150}], observed_at=BASE - timedelta(hours=24), path=path)
    save_video_metrics("UC_A", "A", [{**record, "views": 180, "likes": 4}], observed_at=BASE, path=path)
    save_video_metrics("UC_B", "B", [{**record, "views": 999}], observed_at=BASE, path=path)
    a = list_video_metrics("UC_A", now=BASE, path=path)
    b = list_video_metrics("UC_B", now=BASE, path=path)
    assert a["summary"]["total_views"] == 180
    assert a["items"][0]["views_24h"] == 30
    assert a["items"][0]["views_7d"] == 80
    assert a["items"][0]["views_since_previous"] == 30
    assert b["items"][0]["views"] == 999
    assert recently_synced("UC_A", now=BASE + timedelta(minutes=1), path=path)


def test_refresh_authorization_and_does_not_resync_recent(monkeypatch, tmp_path):
    import src.api.main as api
    monkeypatch.setenv("API_AUTH_TOKEN", "test-secret")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "server.db"))
    monkeypatch.setattr(api, "_verified_account_channel",
                        lambda mode, *args: {"channel_id": "UC_test", "channel_title": "채널"} if mode == "personal" else None)
    hit = []
    def fake_fetch(**kwargs):
        hit.append(True)
        return {"channel_id": "UC_test", "channel_title": "채널",
                "videos": [{"video_id": VIDEO1, "title": "my upload", "views": 123,
                            "likes": 2, "comments": 0, "privacy_status": "public",
                            "published_at": "2026-10-01T00:00:00Z"}], "limit_reached": False}
    monkeypatch.setattr(api, "fetch_my_videos", fake_fetch)
    client = TestClient(app)
    assert client.get("/my-videos").status_code == 401
    headers = {"X-API-Key": "test-secret", "X-AI-Comment-Account-Mode": "demo"}
    assert client.post("/my-videos/refresh", headers=headers).status_code == 403
    headers["X-AI-Comment-Account-Mode"] = "personal"
    first = client.post("/my-videos/refresh", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["summary"]["tracked_count"] == 1
    assert first.json()["checked_count"] == 1
    second = client.post("/my-videos/refresh", headers=headers)
    assert second.json()["cached"] is True
    assert hit == [True]
    assert client.get("/my-videos", headers=headers).json()["channel_id"] == "UC_test"


def test_manual_registration_must_match_authenticated_channel(monkeypatch, tmp_path):
    import src.api.main as api
    monkeypatch.setenv("API_AUTH_TOKEN", "test-secret")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "server.db"))
    monkeypatch.setattr(api, "_verified_account_channel",
                        lambda mode, *args: {"channel_id": "UC_test"} if mode == "personal" else None)
    monkeypatch.setattr(api, "fetch_owned_video",
                        lambda video_id, **kwargs: {"channel_id": "UC_OTHER", "channel_title": "other", "videos": [item(video_id)]})
    headers = {"X-API-Key": "test-secret", "X-AI-Comment-Account-Mode": "personal"}
    c = TestClient(app)
    assert c.post("/my-videos/track", json={"video_id": VIDEO1}, headers=headers).status_code == 403
    assert c.post("/my-videos/track", json={"video_id": "invalid"}, headers=headers).status_code == 422
    assert c.get("/my-videos", headers=headers).json()["items"] == []
