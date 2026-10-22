from fastapi.testclient import TestClient
import src.api.main as api_main

client = TestClient(api_main.app)


def test_private_generation_does_not_leak_into_legacy_history(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_COMMENT_DB_PATH", str(tmp_path / "account.db"))
    def fake_rank(text, *, generation_context, top_k, generation_client=None, persona=None):
        return {
            "recommendations": [
                {"rank": i, "type": "general", "comment": f"private {i}", "predicted_score": 51.5}
                for i in range(1, top_k + 1)
            ],
            "candidate_count": top_k,
            "safe_candidate_count": top_k,
            "blocked_candidate_count": 0,
            "trace": {"safety_blocked_count": 0, "duplicate_candidate_count": 0, "candidates": []},
        }
    monkeypatch.setattr(api_main, "recommend_comments_with_meta", fake_rank)
    response = client.post(
        "/recommend",
        headers={"X-AI-Comment-Private-History": "1"},
        json={"post_text": "새 회원 계정의 비공개 생성 요청", "top_k": 3},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["analysis_id"].startswith("a_")
    assert len(result["recommendations"]) == 3
    assert all(r["id"].startswith("r_") for r in result["recommendations"])
    assert client.get("/analyses").json()["items"] == []
    assert client.get("/dashboard/summary").json()["analysis_count"] == 0
    assert client.get("/comments").json()["total"] == 0
