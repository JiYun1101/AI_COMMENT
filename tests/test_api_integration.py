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
    trace_candidates = [
        {
            "sequence": index,
            "attempt": 1,
            "type": item["type"],
            "comment": item["comment"],
            "safety": "passed",
            "safety_reason": None,
            "duplicate": False,
            "ranker_score": item["predicted_score"],
            "selected": True,
            "final_rank": item["rank"],
        }
        for index, item in enumerate(recommendations, start=1)
    ]
    return {
        "recommendations": recommendations,
        "candidate_count": top_k * 2,
        "safe_candidate_count": top_k * 2,
        "blocked_candidate_count": 0,
        "trace": {
            "safety_blocked_count": 0,
            "duplicate_candidate_count": 0,
            "candidates": trace_candidates,
        },
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
    assert body["resolved_category"] == "travel"
    assert body["context"]["primary_category"] == "travel"
    assert "travel" in body["context"]["topics"]
    assert body["generation"]["generator"] == "llm"
    assert body["generation"]["returned_count"] == 10
    assert len(body["recommendations"]) == 10
    assert body["analysis_id"].startswith("a_")
    assert all(item["id"].startswith("r_") for item in body["recommendations"])
    assert len(body["trace"]["candidates"]) == 10
    assert all(item["selected"] for item in body["trace"]["candidates"])
    assert body["trace"]["safety_blocked_count"] == 0

    analyses = client.get("/analyses?limit=3")
    assert analyses.json()["items"][0]["id"] == body["analysis_id"]
    detail = client.get(f"/analyses/{body['analysis_id']}")
    assert detail.status_code == 200
    assert detail.json()["additional_context"] == "가족 여행 관점"
    assert detail.json()["requested_count"] == 10
    assert detail.json()["context_summary"]["primary_category"] == "travel"

    comments = client.get("/comments", params={"category": "travel", "min_score": 80})
    assert comments.status_code == 200
    assert comments.json()["total"] > 0
    recommendation_id = body["recommendations"][0]["id"]
    feedback = client.post(f"/recommendations/{recommendation_id}/feedback", json={"useful": True})
    assert feedback.json()["feedback"] == "useful"
    summary = client.get("/dashboard/summary")
    assert summary.json()["analysis_count"] == 1
    assert summary.json()["recommendation_count"] == 10
    assert summary.json()["helpful_rate"] == 100.0


def test_additional_context_is_separate_from_source_and_added_once_for_ranking(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "separate-context.db"))
    captured = {}

    def fake_context_builder(reference_text, *, youtube_context=None, additional_context=None, category_hint=None):
        captured["source_reference_text"] = reference_text
        captured["additional_context"] = additional_context
        return {
            "source": {"type": "manual", "title": reference_text, "additional_context": additional_context},
            "youtube": {"category_name": None},
            "format": {"kind": "unknown", "broadcast": "unknown"},
            "temporal": {"freshness": "unknown"},
            "popularity": {"hype_label": "normal", "hype_score": 0.0},
            "content": {"topics": ["software"], "content_styles": []},
            "historical_comments": {"matched_count": 0, "coverage": "none"},
            "primary_category": "software",
        }

    def fake_ranker(post_text: str, *, generation_context: dict, top_k: int):
        captured["ranking_reference_text"] = post_text
        return _fake_ranked(post_text, generation_context=generation_context, top_k=top_k)

    monkeypatch.setattr(api_main, "build_generation_context", fake_context_builder)
    monkeypatch.setattr(api_main, "recommend_comments_with_meta", fake_ranker)

    response = client.post(
        "/recommend",
        json={
            "post_text": "React 상태 관리 패턴을 설명합니다.",
            "additional_context": "주니어 개발자 관점",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    assert captured["source_reference_text"] == "React 상태 관리 패턴을 설명합니다."
    assert captured["additional_context"] == "주니어 개발자 관점"
    assert captured["ranking_reference_text"].count("주니어 개발자 관점") == 1
    assert response.json()["post_text"].count("주니어 개발자 관점") == 1


def test_empty_recommend_request_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "empty.db"))
    response = client.post("/recommend", json={"top_k": 5})
    assert response.status_code == 422
