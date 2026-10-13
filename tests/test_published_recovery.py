from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from src.api.main import app, _track_published_comment
from src.api.schemas import YouTubeCommentPublishRequest
from src.storage.published_store import record_published_comment, list_published_comments

client = TestClient(app)
VIDEO = "dQw4w9WgXcQ"


def test_recovered_comment_is_idempotent_and_retains_post_time(tmp_path):
    path = tmp_path / "recover.db"
    old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    data = dict(video_id=VIDEO, comment_id="oldcomment", comment="댓글",
                comment_url="https://www.youtube.com/watch?v=" + VIDEO,
                account_mode="personal", published_at=old, path=path)
    first = record_published_comment(**data)
    second = record_published_comment(**data)
    assert first == second
    rows = list_published_comments(account_mode="personal", path=path)
    assert len(rows) == 1
    assert rows[0]["published_at"] == old


def test_restore_endpoint_authenticates_and_prevents_duplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "owner-test-token")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "app.db"))

    def verify(**kwargs):
        return {"video_id": VIDEO, "comment_id": "oldcomment", "comment": "댓글",
                "comment_url": "https://www.youtube.com/watch?v=" + VIDEO,
                "published_at": datetime.now(timezone.utc).isoformat()}

    monkeypatch.setattr("src.api.main.fetch_owned_youtube_comment", verify)
    monkeypatch.setattr("src.api.main._verified_account_channel", lambda mode, *args: {"channel_id": "my-channel"} if mode == "personal" else None)
    data = {"video_id": VIDEO, "comment_id": "oldcomment"}
    assert client.post("/my-comments/recover", json=data).status_code == 401
    assert client.post("/my-comments/recover", json=data,
                       headers={"X-API-Key": "owner-test-token"}).status_code == 403
    headers = {"X-API-Key": "owner-test-token", "X-AI-Comment-Account-Mode": "personal"}
    one = client.post("/my-comments/recover", json=data, headers=headers)
    two = client.post("/my-comments/recover", json=data, headers=headers)
    assert one.status_code == 200
    assert two.status_code == 200
    assert one.json()["id"] == two.json()["id"]
    assert client.get("/my-comments", headers=headers).json()["summary"]["tracked_count"] == 1


def test_youtube_recovery_rejects_other_authors_and_video_ids(monkeypatch):
    import pytest
    import src.youtube.comments as youtube
    for channel, video in [("other", VIDEO), ("mine", "9bZkp7q19f0")]:
        replies = iter([
            {"items": [{"id": "mine"}]},
            {"items": [{"id": "myold", "snippet": {
                "authorChannelId": {"value": channel}, "videoId": video, "textOriginal": "text"
            }}]},
        ])
        monkeypatch.setattr(youtube, "_authorized_json", lambda *a, **kw: next(replies))
        with pytest.raises(youtube.YouTubeCommentPublishError):
            youtube.fetch_owned_youtube_comment(comment_id="myold", video_id=VIDEO)


def test_published_but_untracked_returns_warning(monkeypatch):
    def fail(**kwargs):
        raise OSError("db unavailable")
    monkeypatch.setattr("src.api.main.record_published_comment", fail)
    data = YouTubeCommentPublishRequest(video_id=VIDEO, channel_id="UCtest", comment="success")
    result = _track_published_comment({"posted": True, "video_id": VIDEO, "comment_id": "abc"}, data, "personal")
    assert result["tracked"] is False
    assert "tracking_warning" in result


def test_health_warns_if_durable_storage_not_confirmed(monkeypatch):
    monkeypatch.delenv("AI_COMMENT_STORAGE_PERSISTENT", raising=False)
    assert client.get("/health").json()["storage"]["persistent"] is False
