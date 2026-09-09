import pytest
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


def test_youtube_comment_publish_endpoint_uses_authenticated_publisher(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "test-token")
    captured = {}

    def fake_publish(**kwargs):
        captured.update(kwargs)
        return {
            "posted": True,
            "video_id": kwargs["video_id"],
            "comment_id": "comment-123",
            "comment": kwargs["comment"],
            "comment_url": f"https://www.youtube.com/watch?v={kwargs['video_id']}&lc=comment-123",
        }

    monkeypatch.setattr(api_main, "publish_youtube_comment", fake_publish)
    response = client.post(
        "/youtube/comments",
        json={
            "video_id": "dQw4w9WgXcQ",
            "channel_id": "UC-test-channel",
            "comment": "추천 결과를 실제 댓글로 게시합니다.",
        },
        headers={"X-API-Key": "test-token"},
    )

    assert response.status_code == 200
    assert response.json()["posted"] is True
    assert response.json()["comment_id"] == "comment-123"
    assert captured == {
        "video_id": "dQw4w9WgXcQ",
        "channel_id": "UC-test-channel",
        "comment": "추천 결과를 실제 댓글로 게시합니다.",
    }


def _publish_payload():
    return {
        "video_id": "dQw4w9WgXcQ",
        "channel_id": "UC-test-channel",
        "comment": "추천 결과를 실제 댓글로 게시합니다.",
    }


def test_publish_rejects_wrong_api_key(monkeypatch):
    """토큰이 설정된 경우 잘못된 키로는 사용자 계정에 접근할 수 없어야 한다."""
    monkeypatch.setenv("API_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(
        api_main,
        "publish_youtube_comment",
        lambda **_: pytest.fail("인증 실패 시 publisher가 호출되면 안 된다"),
    )

    response = client.post(
        "/youtube/comments", json=_publish_payload(), headers={"X-API-Key": "wrong"}
    )

    assert response.status_code == 401


def test_publish_rejects_remote_client_without_token(monkeypatch):
    """토큰 미설정 시에는 loopback 요청만 허용한다."""
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(
        api_main,
        "publish_youtube_comment",
        lambda **_: pytest.fail("원격 요청에서 publisher가 호출되면 안 된다"),
    )
    remote_client = TestClient(api_main.app, client=("203.0.113.5", 51000))

    response = remote_client.post("/youtube/comments", json=_publish_payload())

    assert response.status_code == 403


def test_publish_allows_loopback_client_without_token(monkeypatch):
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(
        api_main,
        "publish_youtube_comment",
        lambda **kwargs: {"posted": True, "comment_id": "c1", **kwargs},
    )
    local_client = TestClient(api_main.app, client=("127.0.0.1", 51000))

    response = local_client.post("/youtube/comments", json=_publish_payload())

    assert response.status_code == 200
    assert response.json()["posted"] is True


def test_oauth_endpoints_are_protected(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "test-token")

    assert client.get("/youtube/oauth/start").status_code == 401
    assert client.post("/youtube/oauth/disconnect").status_code == 401
    # 읽기 전용 상태 조회는 계정을 건드리지 않으므로 열려 있다.
    assert client.get("/youtube/oauth/status").status_code == 200
