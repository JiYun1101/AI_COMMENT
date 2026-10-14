from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.storage.published_store import (
    delete_owned_published_record, list_published_comments,
    record_published_comment, update_owned_published_text,
)
from src.youtube.comments import (
    YouTubeCommentPublishError, delete_owned_youtube_comment,
    edit_owned_youtube_comment,
)


def test_youtube_edit_delete_only_for_verified_author(monkeypatch):
    import src.youtube.comments as youtube
    requests_seen = []

    def fake_json(http, url, *, params, **kwargs):
        if url == youtube.YOUTUBE_CHANNELS_URL:
            return {"items": [{"id": "my-channel", "snippet": {"title": "Mine"}}]}
        assert params["id"] == "mine-comment"
        return {"items": [{"id": "mine-comment", "snippet": {
            "authorChannelId": {"value": "my-channel"},
            "textOriginal": "before",
        }}]}

    def fake_request(http, method, url, *, params, **kwargs):
        requests_seen.append((method, url, params, kwargs))
        return SimpleNamespace(status_code=200 if method == "PUT" else 204)

    monkeypatch.setattr(youtube, "_authorized_json", fake_json)
    monkeypatch.setattr(youtube, "_authorized_request", fake_request)
    changed = edit_owned_youtube_comment("mine-comment", "after")
    assert changed["owner_channel_id"] == "my-channel"
    assert changed["comment"] == "after"
    method, url, params, opts = requests_seen[0]
    assert method == "PUT" and url == youtube.YOUTUBE_COMMENTS_URL
    assert params == {"part": "snippet"}
    assert opts["json"] == {"id": "mine-comment", "snippet": {"textOriginal": "after"}}

    deleted = delete_owned_youtube_comment("mine-comment")
    assert deleted["owner_channel_id"] == "my-channel"
    assert requests_seen[1][0] == "DELETE"
    assert requests_seen[1][2] == {"id": "mine-comment"}


def test_rejects_mutation_of_another_channels_comment(monkeypatch):
    import src.youtube.comments as youtube
    def fake_json(http, url, *, params, **kwargs):
        return {"items": [{"id": "my-channel"}]} if url == youtube.YOUTUBE_CHANNELS_URL else {
            "items": [{"id": "mine-comment", "snippet": {
                "authorChannelId": {"value": "other-channel"},
            }}],
        }
    monkeypatch.setattr(youtube, "_authorized_json", fake_json)
    monkeypatch.setattr(youtube, "_authorized_request",
                        lambda *args, **kwargs: pytest.fail("No mutation for other channel"))
    with pytest.raises(YouTubeCommentPublishError) as exc:
        delete_owned_youtube_comment("mine-comment")
    assert exc.value.status_code == 403


def test_tracking_mutations_are_scoped_to_verified_account(tmp_path):
    path = tmp_path / "tracked.db"
    record_published_comment(
        video_id="dQw4w9WgXcQ", comment_id="owned", comment="before",
        comment_url=None, account_mode="personal", owner_channel_id="owner-A",
        published_at=datetime.now(timezone.utc).isoformat(), path=path,
    )
    assert not update_owned_published_text("owned", "owner-B", "wrong", path=path)
    assert not delete_owned_published_record("owned", "owner-B", path=path)
    assert update_owned_published_text("owned", "owner-A", "after", path=path)
    assert list_published_comments(owner_channel_id="owner-A", path=path)[0]["comment"] == "after"
    assert delete_owned_published_record("owned", "owner-A", path=path)
    assert not list_published_comments(owner_channel_id="owner-A", path=path)


def test_edit_delete_routes_require_trusted_client_and_personal_account(monkeypatch, tmp_path):
    import src.api.main as api
    monkeypatch.setenv("API_AUTH_TOKEN", "edit-test-token")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "comments.db"))
    actions = []
    monkeypatch.setattr(api, "edit_owned_youtube_comment", lambda cid, text, **kw: (
        actions.append(("edit", cid, text)) or {
            "comment_id": cid, "comment": text.strip(), "owner_channel_id": "mine",
        }
    ))
    monkeypatch.setattr(api, "delete_owned_youtube_comment", lambda cid, **kw: (
        actions.append(("delete", cid)) or {"comment_id": cid, "owner_channel_id": "mine"}
    ))
    http = TestClient(app)
    url = "/my-comments/comment-1"
    assert http.put(url, json={"text": "updated"}).status_code == 401
    assert http.delete(url).status_code == 401
    demo_headers = {"X-API-Key": "edit-test-token"}
    assert http.put(url, json={"text": "updated"}, headers=demo_headers).status_code == 403
    assert http.delete(url, headers=demo_headers).status_code == 403
    assert not actions
    headers = {**demo_headers, "X-AI-Comment-Account-Mode": "personal"}
    edited = http.put(url, json={"text": "updated"}, headers=headers)
    assert edited.status_code == 200
    assert edited.json()["updated"] is True
    deleted = http.delete(url, headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert actions == [("edit", "comment-1", "updated"), ("delete", "comment-1")]
