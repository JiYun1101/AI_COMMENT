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


def test_history_visibility_is_scoped_to_verified_youtube_channel(tmp_path):
    db = tmp_path / "account-history.db"
    a = dict(video_id=VIDEO, comment="A", comment_url=None, account_mode="personal", path=db)
    record_published_comment(comment_id="channel-a-comment", owner_channel_id="UC_a", **a)
    record_published_comment(comment_id="channel-b-comment", owner_channel_id="UC_b", **a)
    assert [row["comment_id"] for row in list_published_comments(
        account_mode="personal", owner_channel_id="UC_a", path=db
    )] == ["channel-a-comment"]
    assert [row["comment_id"] for row in list_published_comments(
        account_mode="personal", owner_channel_id="UC_b", path=db
    )] == ["channel-b-comment"]


def test_oauth_identity_cannot_be_chosen_by_client(monkeypatch):
    from src.youtube import comments as yt
    monkeypatch.setattr(yt, "_authorized_json", lambda *args, **kwargs: {
        "items": [{"id": "UC_signed", "snippet": {"title": "my verified channel"}}],
    })
    identity = yt.authenticated_youtube_channel()
    assert identity == {"channel_id": "UC_signed", "channel_title": "my verified channel"}



def test_batch_youtube_import_restores_only_comments_owned_by_oauth_channel(monkeypatch):
    import src.youtube.comments as youtube
    seen = []
    def fake_authorized(http, url, *, params, **kwargs):
        seen.append((url, params))
        if "channels" in url:
            return {"items": [{"id": "my-channel", "snippet": {"title": "내 채널"}}]}
        if "commentThreads" in url:
            return {"items": [
                {"id": "owned", "snippet": {"videoId": VIDEO, "topLevelComment": {"id": "owned"}}},
                {"id": "stranger", "snippet": {"videoId": VIDEO, "topLevelComment": {"id": "stranger"}}},
            ]}
        return {"items": [
            {"id": "owned", "snippet": {
                "authorChannelId": {"value": "my-channel"}, "videoId": VIDEO,
                "textOriginal": "이미 발행한 댓글", "publishedAt": "2026-10-11T01:02:03Z",
            }},
            {"id": "stranger", "snippet": {
                "authorChannelId": {"value": "another-channel"}, "videoId": VIDEO,
                "textOriginal": "남의 댓글",
            }},
        ]}
    monkeypatch.setattr(youtube, "_authorized_json", fake_authorized)
    verified, rejected, owner = youtube.verify_owned_comment_batch([
        {"video_id": VIDEO, "comment_id": "owned"},
        {"video_id": VIDEO, "comment_id": "stranger"},
        {"video_id": VIDEO, "comment_id": "missing"},
    ])
    assert owner["channel_id"] == "my-channel"
    assert [item["comment_id"] for item in verified] == ["owned"]
    assert [item["comment_id"] for item in rejected] == ["stranger", "missing"]
    assert len(seen) == 3


def test_batch_recovery_registers_only_verified_and_requires_authenticated_personal_mode(monkeypatch, tmp_path):
    import src.api.main as api
    monkeypatch.setenv("API_AUTH_TOKEN", "batch-owner-token")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "data.db"))
    monkeypatch.setattr(api, "verify_owned_comment_batch", lambda rows, **kwargs: ([
        {
            "video_id": VIDEO, "comment_id": "verified-id", "comment": "내 댓글",
            "published_at": "2026-10-10T00:00:00+00:00",
            "comment_url": f"https://www.youtube.com/watch?v={VIDEO}&lc=verified-id",
        }
    ], [{"comment_id": "notmine", "reason": "현재 계정의 댓글이 아님"}], {
        "channel_id": "my-channel", "channel_title": "채널",
    }))
    payload = {"comments": [
        {"video_id": VIDEO, "comment_id": "verified-id"},
        {"video_id": VIDEO, "comment_id": "notmine"},
    ]}
    assert client.post("/my-comments/recover/batch", json=payload).status_code == 401
    assert client.post(
        "/my-comments/recover/batch", json=payload,
        headers={"X-API-Key": "batch-owner-token"},
    ).status_code == 403
    headers = {"X-API-Key": "batch-owner-token", "X-AI-Comment-Account-Mode": "personal"}
    response = client.post("/my-comments/recover/batch", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["registered_count"] == 1
    assert response.json()["failed_count"] == 1
    assert client.post("/my-comments/recover/batch", json=payload, headers=headers).json()["registered_count"] == 1
    assert len(list_published_comments(owner_channel_id="my-channel")) == 1
    assert list_published_comments(owner_channel_id="other-channel") == []


def test_batch_lookup_does_not_combine_id_with_max_results(monkeypatch):
    import src.youtube.comments as youtube
    calls = []
    def fake_json(http, url, *, params, **kwargs):
        calls.append((url, params))
        if url == youtube.YOUTUBE_CHANNELS_URL:
            return {"items": [{"id": "mine", "snippet": {"title": "My channel"}}]}
        return {"items": [{"id": "own", "snippet": {
            "authorChannelId": {"value": "mine"}, "videoId": VIDEO,
            "textOriginal": "hello"}}]}
    monkeypatch.setattr(youtube, "_authorized_json", fake_json)
    verified, rejected, _ = youtube.verify_owned_comment_batch([
        {"video_id": VIDEO, "comment_id": "own"}])
    assert len(verified) == 1 and not rejected
    params = [p for url, p in calls if url == youtube.YOUTUBE_COMMENTS_URL][0]
    assert params["id"] == "own"
    assert "maxResults" not in params

def test_batch_restores_comment_when_comments_endpoint_omits_video_id(monkeypatch):
    import src.youtube.comments as youtube
    calls = []
    def fake_json(http, url, *, params, **kwargs):
        calls.append(url)
        if "channels" in url:
            return {"items": [{"id": "mine", "snippet": {"title": "channel"}}]}
        if "commentThreads" in url:
            return {"items": [{"id": "top-comment", "snippet": {
                "videoId": VIDEO, "topLevelComment": {"id": "top-comment"}}}]}
        return {"items": [{"id": "top-comment", "snippet": {
            "authorChannelId": {"value": "mine"}, "textOriginal": "hello"}}]}
    monkeypatch.setattr(youtube, "_authorized_json", fake_json)
    verified, rejected, _ = youtube.verify_owned_comment_batch([
        {"video_id": VIDEO, "comment_id": "top-comment"}])
    assert len(verified) == 1 and rejected == []
    assert any("commentThreads" in url for url in calls)
    verified, rejected, _ = youtube.verify_owned_comment_batch([
        {"video_id": "9bZkp7q19f0", "comment_id": "top-comment"}])
    assert not verified and len(rejected) == 1
