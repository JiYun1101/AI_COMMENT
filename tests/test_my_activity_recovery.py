from __future__ import annotations

from datetime import datetime, timezone
from fastapi.testclient import TestClient
from src.api.main import app
import src.youtube.comments as yt

client = TestClient(app)
VIDEO = "dQw4w9WgXcQ"
TITLE = "가을 플레이리스트"


def test_pasted_activity_requires_authenticated_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("API_AUTH_TOKEN", "test-secret")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "test.db"))
    request = {"comments": [{"video_title": TITLE, "comment_text": "이 영상 분위기 좋아요"}]}
    assert client.post("/my-comments/recover/activity", json=request).status_code == 401
    assert client.post("/my-comments/recover/activity", json=request,
                       headers={"X-API-Key": "test-secret"}).status_code == 403


def test_my_activity_resolves_unique_title_and_own_exact_comment(monkeypatch, tmp_path):
    monkeypatch.setenv("API_AUTH_TOKEN", "test-secret")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(yt, "authenticated_youtube_channel",
                        lambda **kwargs: {"channel_id": "UC_mine", "channel_title": "mine"})
    requests = []
    def mock_youtube(http, url, *, params, failure, **oauth):
        requests.append((url, params))
        if url.endswith("/search"):
            return {"items": [{"id": {"videoId": VIDEO}, "snippet": {"title": TITLE}}]}
        if url.endswith("/commentThreads"):
            return {"items": [
                {"snippet": {"topLevelComment": {"id": "comment-123", "snippet": {
                    "authorChannelId": {"value": "UC_mine"},
                    "textOriginal": "이 영상 분위기 좋아요",
                    "publishedAt": "2026-10-07T11:38:00Z",
                }}}},
                {"snippet": {"topLevelComment": {"id": "not-me", "snippet": {
                    "authorChannelId": {"value": "UC_other"},
                    "textOriginal": "이 영상 분위기 좋아요",
                }}}},
            ]}
        raise AssertionError("unexpected URL")
    monkeypatch.setattr(yt, "_authorized_json", mock_youtube)
    headers = {"X-API-Key": "test-secret", "X-AI-Comment-Account-Mode": "personal"}
    request = {"comments": [{"video_title": TITLE, "comment_text": "이 영상 분위기 좋아요"}]}
    first = client.post("/my-comments/recover/activity", json=request, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["registered_count"] == 1
    assert first.json()["failed_count"] == 0
    again = client.post("/my-comments/recover/activity", json=request, headers=headers)
    assert again.json()["registered_count"] == 1
    # Only one stable YouTube comment ID, even after importing the activity twice.
    monkeypatch.setattr("src.api.main._verified_account_channel",
                        lambda *a, **kw: {"channel_id": "UC_mine"})
    rows = client.get("/my-comments", headers=headers).json()["items"]
    assert len(rows) == 1
    assert rows[0]["comment_id"] == "comment-123"
    assert rows[0]["published_at"] == "2026-10-07T11:38:00Z"
    assert any(url.endswith("/search") for url, params in requests)


def test_pasted_activity_does_not_store_uncertain_or_other_account_comments(monkeypatch):
    monkeypatch.setattr(yt, "authenticated_youtube_channel",
                        lambda **kwargs: {"channel_id": "UC_mine", "channel_title": "mine"})
    def mock_youtube(http, url, *, params, failure, **oauth):
        if url.endswith("/search"):
            return {"items": [{"id": {"videoId": VIDEO}, "snippet": {"title": TITLE}}]}
        return {"items": [{"snippet": {"topLevelComment": {"id": "bad-id", "snippet": {
            "authorChannelId": {"value": "UC_other"}, "textOriginal": "똑같은 댓글",
        }}}}]}
    monkeypatch.setattr(yt, "_authorized_json", mock_youtube)
    good, errors, _ = yt.find_owned_comments_from_activity(
        [{"video_title": TITLE, "comment_text": "똑같은 댓글"}],
    )
    assert good == []
    assert len(errors) == 1


def test_pasted_activity_rejects_ambiguous_titles_and_limits(monkeypatch):
    monkeypatch.setattr(yt, "authenticated_youtube_channel",
                        lambda **kwargs: {"channel_id": "UC_mine", "channel_title": "mine"})
    monkeypatch.setattr(yt, "_authorized_json",
                        lambda *args, **kwargs: {"items": [
                            {"id": {"videoId": VIDEO}, "snippet": {"title": TITLE}},
                            {"id": {"videoId": "9bZkp7q19f0"}, "snippet": {"title": TITLE}},
                        ]})
    rows, failures, _ = yt.find_owned_comments_from_activity(
        [{"video_title": TITLE, "comment_text": "댓글 하나"}],
    )
    assert rows == []
    assert "여러 개" in failures[0]["reason"]
    import pytest
    with pytest.raises(yt.YouTubeCommentPublishError):
        yt.find_owned_comments_from_activity(
            [{"video_title": "test" + str(i), "comment_text": "댓글"} for i in range(11)]
        )
