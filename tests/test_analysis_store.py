from src.storage.analysis_store import (
    dashboard_summary,
    get_analysis,
    list_analyses,
    list_comments,
    save_analysis,
    set_feedback,
)


def _recommendations():
    return [
        {"rank": 1, "type": "insight", "comment": "제주 여행 동선이 정말 참고가 되네요.", "predicted_score": 84.5},
        {"rank": 2, "type": "question", "comment": "갈치조림 맛집은 예약이 필요한가요?", "predicted_score": 73.2},
    ]


def test_persistence_history_filters_and_feedback(tmp_path):
    db_path = tmp_path / "test.db"
    analysis_id, stored = save_analysis(
        source_type="youtube",
        source_text="제주 여행 브이로그",
        category="vlog",
        recommendations=_recommendations(),
        youtube_context={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "video_id": "dQw4w9WgXcQ",
            "title": "제주 여행 브이로그",
            "channel": "여행채널",
            "thumbnail_url": "https://img.example/thumb.jpg",
        },
        path=db_path,
    )

    assert analysis_id.startswith("a_")
    assert all(item["id"].startswith("r_") for item in stored)
    recent = list_analyses(limit=3, path=db_path)
    assert recent[0]["id"] == analysis_id
    assert recent[0]["recommendation_count"] == 2
    detail = get_analysis(analysis_id, path=db_path)
    assert detail is not None
    assert len(detail["recommendations"]) == 2
    filtered = list_comments(query="갈치", category="vlog", min_score=70, path=db_path)
    assert filtered["total"] == 1
    assert filtered["items"][0]["type"] == "question"
    feedback = set_feedback(stored[0]["id"], useful=True, path=db_path)
    assert feedback == {"id": stored[0]["id"], "feedback": "useful"}
    summary = dashboard_summary(path=db_path)
    assert summary["analysis_count"] == 1
    assert summary["recommendation_count"] == 2
    assert summary["feedback_count"] == 1
    assert summary["helpful_rate"] == 100.0
