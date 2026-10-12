from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import src.api.main as api_main
from src.storage.analysis_store import save_analysis
from src.storage.published_store import (
    apply_comment_metrics,
    comment_ids_to_refresh,
    list_published_comments,
    published_summary,
    record_published_comment,
    spearman,
)

client = TestClient(api_main.app)


def _recommendations(db, scores):
    _, stored = save_analysis(
        source_type="youtube",
        source_text="영상",
        category="Gaming",
        recommendations=[
            {"rank": index, "type": "question" if index % 2 else "empathy", "comment": f"댓글 {index}", "predicted_score": score}
            for index, score in enumerate(scores, start=1)
        ],
        youtube_context={"video_id": "dQw4w9WgXcQ", "title": "테스트 영상"},
        path=db,
    )
    return stored


def test_spearman_handles_ties_and_small_samples():
    assert spearman([1, 2], [1, 2]) is None
    assert spearman([1, 2, 3], [5, 5, 5]) is None
    assert spearman([10, 20, 30, 40], [0, 1, 1, 9]) == 0.949


def test_metrics_fix_milestones_once_and_mark_missing(tmp_path):
    db = tmp_path / "store.db"
    stored = _recommendations(db, [80.0, 60.0])
    record_published_comment(
        video_id="dQw4w9WgXcQ", comment_id="c1", comment="댓글 1", comment_url=None,
        account_mode="demo", recommendation_id=stored[0]["id"], path=db,
    )
    record_published_comment(
        video_id="dQw4w9WgXcQ", comment_id="c2", comment="댓글 2", comment_url=None,
        account_mode="demo", recommendation_id="r_unknown", path=db,
    )

    published_at = datetime.fromisoformat(list_published_comments(path=db)[0]["published_at"])
    apply_comment_metrics(["c1", "c2"], {"c1": {"like_count": 3, "reply_count": 1}}, now=published_at + timedelta(hours=2), path=db)
    apply_comment_metrics(["c1"], {"c1": {"like_count": 9, "reply_count": 1}}, now=published_at + timedelta(hours=30), path=db)
    apply_comment_metrics(["c1"], {"c1": {"like_count": 12, "reply_count": 2}}, now=published_at + timedelta(hours=40), path=db)

    rows = {row["comment_id"]: row for row in list_published_comments(path=db)}
    assert rows["c1"]["like_count"] == 12
    assert rows["c1"]["likes_24h"] == 9
    assert rows["c1"]["likes_7d"] is None
    assert rows["c1"]["predicted_score"] == 80.0
    assert rows["c1"]["video_title"] == "테스트 영상"
    assert rows["c2"]["status"] == "missing"
    assert rows["c2"]["recommendation_id"] is None

    summary = published_summary(list(rows.values()))
    assert summary["tracked_count"] == 2
    assert summary["measured_count"] == 1
    assert summary["missing_count"] == 1
    assert summary["replied_rate"] == 100.0


def test_refresh_skips_recently_checked_comments(tmp_path):
    db = tmp_path / "store.db"
    record_published_comment(
        video_id="dQw4w9WgXcQ", comment_id="c1", comment="댓글", comment_url=None, account_mode="personal", path=db,
    )
    assert comment_ids_to_refresh(account_mode="personal", path=db) == ["c1"]
    assert comment_ids_to_refresh(account_mode="demo", path=db) == []
    apply_comment_metrics(["c1"], {"c1": {"like_count": 1, "reply_count": 0}}, now=datetime.now(timezone.utc), path=db)
    assert comment_ids_to_refresh(account_mode="personal", path=db) == []


def test_publish_tracks_comment_and_refresh_reads_real_reactions(tmp_path, monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "test-key")
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("DEMO_YOUTUBE_API_KEY", "demo-key")
    stored = _recommendations(tmp_path / "api.db", [70.0])

    monkeypatch.setattr(
        api_main,
        "publish_demo_youtube_comment",
        lambda **kwargs: {
            "posted": True,
            "account_mode": "demo",
            "video_id": kwargs["video_id"],
            "comment_id": "posted-1",
            "comment": kwargs["comment"],
            "comment_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&lc=posted-1",
        },
    )
    captured = {}

    def fake_metrics(comment_ids, *, api_key):
        captured["ids"], captured["key"] = comment_ids, api_key
        return {"posted-1": {"like_count": 5, "reply_count": 1}}

    monkeypatch.setattr(api_main, "fetch_comment_metrics", fake_metrics)

    posted = client.post(
        "/youtube/comments",
        headers={"X-AI-Comment-Account-Mode": "demo"},
        json={
            "video_id": "dQw4w9WgXcQ",
            "channel_id": "UC-test",
            "comment": "댓글 1",
            "recommendation_id": stored[0]["id"],
        },
    )
    assert posted.status_code == 200
    assert posted.json()["tracked"] is True

    refreshed = client.post("/my-comments/refresh", headers={"X-AI-Comment-Account-Mode": "demo", "X-API-Key": "test-key"})
    assert refreshed.status_code == 200
    assert captured == {"ids": ["posted-1"], "key": "demo-key"}
    item = refreshed.json()["items"][0]
    assert item["like_count"] == 5 and item["predicted_score"] == 70.0

    personal = client.get("/my-comments", headers={"X-AI-Comment-Account-Mode": "personal", "X-API-Key": "test-key"})
    assert personal.json()["items"] == []


def test_demo_account_cannot_post_creator_replies():
    response = client.post(
        "/creator/inbox/replies",
        headers={"X-AI-Comment-Account-Mode": "demo"},
        json={"parent_id": "thread-1", "text": "감사합니다!"},
    )
    assert response.status_code == 403
