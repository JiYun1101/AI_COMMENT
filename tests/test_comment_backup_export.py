from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.api.main import app
from src.storage.published_store import record_published_comment


def test_export_requires_auth_and_limits_data_to_connected_youtube_channel(monkeypatch, tmp_path):
    import src.api.main as api

    monkeypatch.setenv("API_AUTH_TOKEN", "backup-secret")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "backup.db"))
    monkeypatch.setattr(api, "_verified_account_channel",
                        lambda mode, *args: {"channel_id": "owner-one"})
    for comment_id, owner in (("mine-1", "owner-one"), ("not-mine", "owner-two")):
        record_published_comment(
            video_id="dQw4w9WgXcQ", comment_id=comment_id,
            comment=f"text {comment_id}", account_mode="personal",
            owner_channel_id=owner, comment_url=None,
            published_at=datetime.now(timezone.utc).isoformat(),
        )

    http = TestClient(app)
    url = "/my-comments/export"
    assert http.get(url).status_code == 401
    demo = http.get(url, headers={"X-API-Key": "backup-secret"})
    assert demo.status_code == 403
    verified = http.get(url, headers={
        "X-API-Key": "backup-secret", "X-AI-Comment-Account-Mode": "personal",
    })
    assert verified.status_code == 200
    assert verified.headers["cache-control"] == "no-store"
    data = verified.json()
    assert data["format"] == "ai-comment-published-backup-v1"
    assert data["channel_id"] == "owner-one"
    assert [c["comment_id"] for c in data["comments"]] == ["mine-1"]
    assert "predicted_score" in data["comments"][0]
    assert "likes_24h" in data["comments"][0]
