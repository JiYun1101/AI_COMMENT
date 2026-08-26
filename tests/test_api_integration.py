from fastapi.testclient import TestClient

import src.api.main as api_main

client = TestClient(api_main.app)


def _fake_ranked(post_text: str, *, generation_context: dict, top_k: int):
    recommendations = [
        {
            "rank": index,
            "type": "insight" if index % 2 else "question",
            "comment": f"{generation_context['primary_category']} 문맥 추천 댓글 {index}",
            "predicted_score": 90.0 - index,
        }
        for index in range(1, top_k + 1)
    ]
    return {
        "recommendations": recommendations,
        "candidate_count": top_k * 2,
        "safe_candidate_count": top_k * 2,
        "blocked_candidate_count": 0,
    }


def test_recommend_persists_context_and_dashboard_uses_real_data(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setattr(api_main, "recommend_comments_with_meta", _fake_ranked)
    monkeypatch.setattr(
        "src.recommender.generation_context.build_historical_profile",
        lambda *args, **kwargs: {"coverage": "matched_legacy_category", "matched_count": 5, "reference_examples": []},
    )
    response = client.post(
        "/recommend",
        json={
            "post_text": "제주 여행 브이로그에서 갈치조림 맛집을 소개합니다.",
            "additional_context": "가족 여행 관점",
            "category": "vlog",
            "top_k": 10,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["resolved_category"] == "vlog"
    assert body["context"]["primary_category"] == "vlog"
    assert "travel" in body["context"]["topics"]
    assert body["generation"]["generator"] == "llm"
    assert body["generation"]["returned_count"] == 10
    assert len(body["recommendations"]) == 10
    assert body["analysis_id"].startswith("a_")
    assert all(item["id"].startswith("r_") for item in body["recommendations"])

    analyses = client.get("/analyses?limit=3")
    assert analyses.json()["items"][0]["id"] == body["analysis_id"]
    detail = client.get(f"/analyses/{body['analysis_id']}")
    assert detail.status_code == 200
    assert detail.json()["additional_context"] == "가족 여행 관점"
    assert detail.json()["requested_count"] == 10
    assert detail.json()["context_summary"]["primary_category"] == "vlog"

    comments = client.get("/comments", params={"category": "vlog", "min_score": 80})
    assert comments.status_code == 200
    assert comments.json()["total"] > 0
    recommendation_id = body["recommendations"][0]["id"]
    feedback = client.post(f"/recommendations/{recommendation_id}/feedback", json={"useful": True})
    assert feedback.json()["feedback"] == "useful"
    summary = client.get("/dashboard/summary")
    assert summary.json()["analysis_count"] == 1
    assert summary.json()["recommendation_count"] == 10
    assert summary.json()["helpful_rate"] == 100.0


def test_empty_recommend_request_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "empty.db"))
    response = client.post("/recommend", json={"top_k": 5})
    assert response.status_code == 422
