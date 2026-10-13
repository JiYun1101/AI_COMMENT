from __future__ import annotations

from fastapi.testclient import TestClient

import src.api.main as api_main
from src.audience.reactions import (
    build_observation_report, classify_intent, classify_observed,
    compare_distributions, summarize_intents,
)
from src.storage.analysis_store import save_analysis
from src.storage.audience_store import list_audience_observations, read_audience_observation

client = TestClient(api_main.app)
VIDEO_ID = "dQw4w9WgXcQ"


def sample_threads():
    return [
        {"id": "a", "text": "이 제품 가격 얼마예요?", "like_count": 12, "reply_count": 2},
        {"id": "b", "text": "너무 불편했어요", "like_count": 4, "reply_count": 0},
        {"id": "c", "text": "좋은 영상 감사합니다!", "like_count": 10, "reply_count": 0},
        {"id": "d", "text": "일반적인 이야기", "like_count": 1, "reply_count": 0},
    ]


def test_classification_is_heuristic_and_does_not_label_unknown_as_praise():
    assert classify_intent("이 제품 가격 얼마예요?") == "purchase"
    assert classify_intent("이해가 안 돼요") == "confusion"
    assert classify_intent("언제 올라오나요?") == "question"
    assert classify_intent("좋은 영상 감사합니다") == "praise"
    assert classify_intent("이건 최악이에요") == "complaint"
    assert classify_intent("불법 조작입니다") == "risk"
    assert classify_intent("평범한 표현") == "other"
    assert classify_intent("", "question") == "other"


def test_actual_counts_dedupe_and_bound_sample_size():
    rows = classify_observed(sample_threads() + [sample_threads()[0]])
    assert len(rows) == 4
    assert "author" not in rows[0]
    assert summarize_intents(rows)["total"] == 4
    long_rows = [{"id": str(i), "text": "좋은 영상"} for i in range(150)]
    assert len(classify_observed(long_rows)) == 100


def test_comparison_is_explicitly_not_predictive_accuracy():
    report = build_observation_report(
        VIDEO_ID, sample_threads(),
        recommendations=[
            {"comment": "궁금합니다?", "type": "question"},
            {"comment": "잘 봤어요", "type": "empathy"},
        ],
    )
    assert report["observed"]["total"] == 4
    assert report["expected"]["total"] == 2
    assert report["comparison"]["method"] == "generated_top_k_vs_public_comment_sample"
    assert "정확도" in report["comparison"]["warning"]
    delta = {item["key"]: item["delta_percentage_points"] for item in report["comparison"]["distribution"]}
    assert delta["purchase"] == 25
    assert delta["question"] == -50
    assert report["comparison"]["sample_difference_points"] >= 0

    empty = build_observation_report(VIDEO_ID, [], [])
    assert empty["comparison"] is None


def test_observed_endpoint_works_without_llm_and_persists_only_with_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "audience.db"))
    monkeypatch.setenv("API_AUTH_TOKEN", "private-test-token")
    monkeypatch.setattr(api_main, "fetch_video_comment_threads", lambda vid, **kw: sample_threads())
    analysis_id, _ = save_analysis(
        source_type="youtube",
        source_text="새 영상",
        category="lifestyle",
        youtube_context={"video_id": VIDEO_ID},
        recommendations=[{"rank": 1, "comment": "재밌는 이야기", "type": "empathy", "predicted_score": 58.0}],
    )
    params = {"video_id": VIDEO_ID, "analysis_id": analysis_id}
    headers = {"X-YouTube-API-Key": "local-test-key", "X-AI-Comment-Account-Mode": "personal"}

    response = client.get("/audience/observed", params=params, headers=headers)
    assert response.status_code == 200
    assert response.json()["observed"]["total"] == 4
    assert response.json()["comparison"] is not None
    assert list_audience_observations(VIDEO_ID) == []

    assert client.post("/audience/observations", params=params, headers=headers).status_code == 401
    saved = client.post("/audience/observations", params=params, headers={**headers, "X-API-Key": "private-test-token"})
    assert saved.status_code == 200
    snapshot = saved.json()["snapshot"]
    assert snapshot["sample_count"] == 4
    assert read_audience_observation(snapshot["id"])["report"]["observed"]["total"] == 4
    records = client.get(
        f"/audience/observations/{VIDEO_ID}",
        headers={"X-API-Key": "private-test-token"},
    )
    assert records.status_code == 200
    assert records.json()["items"][0]["id"] == snapshot["id"]
    assert client.get(
        f"/audience/observations/snapshot/{snapshot['id']}",
        headers={"X-API-Key": "private-test-token"},
    ).status_code == 200
    assert "author" not in saved.json()["report"]["comments"][0]


def test_comparison_rejects_mismatched_video_and_missing_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "audience.db"))
    monkeypatch.setenv("API_AUTH_TOKEN", "private-test-token")
    headers = {"X-YouTube-API-Key": "test-key", "X-AI-Comment-Account-Mode": "personal"}
    assert client.get("/audience/observed", params={"video_id": VIDEO_ID, "analysis_id": "not_found"}, headers=headers).status_code == 404
    other, _ = save_analysis(
        source_type="youtube", source_text="other", category="lifestyle",
        youtube_context={"video_id": "9bZkp7q19f0"},
        recommendations=[],
    )
    assert client.get("/audience/observed", params={"video_id": VIDEO_ID, "analysis_id": other}, headers=headers).status_code == 422
