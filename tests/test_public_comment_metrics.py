from __future__ import annotations

from fastapi.testclient import TestClient
from src.api.main import app
from src.youtube import engagement


class StubResponse:
    status_code = 200
    text = ""
    def __init__(self, payload):
        self.payload = payload
    def json(self):
        return self.payload


class StubSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected YouTube call")
        return StubResponse(self.responses.pop(0))


VIDEO = "mJF-S7FfLfM"
COMMENT1 = "UgwmFYoTRZxE6zLIuFR4AaABAg"
COMMENT2 = "Ugwj7ZjFIhCj4Gl-bJN4AaABAg"


def receipts():
    return [
        {"video_id": VIDEO, "comment_id": COMMENT1},
        {"video_id": VIDEO, "comment_id": COMMENT2},
    ]


def test_public_comment_lookup_uses_thread_ids_and_real_counts():
    session = StubSession([{"items": [
        {"id": COMMENT1, "snippet": {
            "videoId": VIDEO,
            "topLevelComment": {"snippet": {"likeCount": 7}},
            "totalReplyCount": 3,
        }},
        {"id": COMMENT2, "snippet": {
            "videoId": VIDEO,
            "topLevelComment": {"snippet": {"likeCount": 0}},
            "totalReplyCount": 0,
        }},
    ]}])
    result = engagement.fetch_public_comment_receipts(
        receipts(), api_key="key", session=session,
    )
    assert result[COMMENT1]["like_count"] == 7
    assert result[COMMENT1]["reply_count"] == 3
    assert result[COMMENT2]["like_count"] == 0
    assert result[COMMENT2]["reply_count"] == 0
    assert len(session.calls) == 1
    path, args = session.calls[0]
    assert path.endswith("/commentThreads")
    assert args["params"]["id"] == COMMENT1 + "," + COMMENT2
    assert "maxResults" not in args["params"]


def test_public_comment_lookup_does_not_accept_another_video_id():
    session = StubSession([
        {"items": [{"id": COMMENT1, "snippet": {
            "videoId": "dQw4w9WgXcQ",
            "topLevelComment": {"snippet": {"likeCount": 400}},
            "totalReplyCount": 40,
        }}]},
        {"items": []},
    ])
    result = engagement.fetch_public_comment_receipts(
        [receipts()[0]], api_key="key", session=session,
    )
    assert result[COMMENT1]["status"] == "unavailable"
    assert result[COMMENT1]["like_count"] is None


def test_reply_comment_falls_back_to_comments_endpoint_and_does_not_fabricate_replies():
    session = StubSession([
        {"items": []},
        {"items": [{"id": COMMENT1, "snippet": {
            "videoId": VIDEO, "parentId": "parent", "likeCount": 2,
        }}]},
    ])
    result = engagement.fetch_public_comment_receipts(
        [receipts()[0]], api_key="key", session=session,
    )
    assert result[COMMENT1]["like_count"] == 2
    assert result[COMMENT1]["reply_count"] is None
    assert session.calls[1][0].endswith("/comments")


def test_public_lookup_requires_key_and_limits_request():
    import pytest
    with pytest.raises(engagement.YouTubeConfigurationError):
        engagement.fetch_public_comment_receipts(receipts(), api_key=None)
    with pytest.raises(ValueError):
        engagement.fetch_public_comment_receipts(receipts() * 26, api_key="key")


def test_endpoint_read_only_and_does_not_require_oauth(monkeypatch, tmp_path):
    import src.api.main as api
    monkeypatch.setenv("API_AUTH_TOKEN", "test-access")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "data.db"))
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-youtube")
    recorded = []
    def fake(receipts, *, api_key):
        recorded.append((receipts, api_key))
        return {COMMENT1: {
            "video_id": VIDEO, "comment_id": COMMENT1, "status": "active",
            "like_count": 5, "reply_count": 1,
        }}
    monkeypatch.setattr(api, "fetch_public_comment_receipts", fake)
    c = TestClient(app)
    route = "/my-comments/public-metrics"
    assert c.post(route, json={"comments": [receipts()[0]]}).status_code == 401
    headers = {"X-API-Key": "test-access", "X-AI-Comment-Account-Mode": "personal"}
    r = c.post(route, json={"comments": [receipts()[0]]}, headers=headers)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["observed_count"] == 1
    assert result["storage"] == "browser_only"
    assert recorded[0][1] == "test-youtube"
    assert not (tmp_path / "data.db").exists()
    assert c.post(route, json={"comments": [{"video_id": "invalid", "comment_id": COMMENT1}]},
                  headers=headers).status_code == 422
    assert c.post(route, json={"comments": receipts() * 26},
                  headers=headers).status_code == 422


def test_no_youtube_key_is_not_disguised_as_success(monkeypatch):
    import src.api.main as api
    monkeypatch.setenv("API_AUTH_TOKEN", "test-access")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("DEMO_YOUTUBE_API_KEY", raising=False)
    c = TestClient(app)
    r = c.post("/my-comments/public-metrics", json={"comments": receipts()},
               headers={"X-API-Key": "test-access",
                        "X-AI-Comment-Account-Mode": "personal"})
    assert r.status_code == 503
    assert "API key" in r.json()["detail"]
