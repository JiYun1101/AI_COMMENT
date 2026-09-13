from src.storage.analysis_store import (
    dashboard_summary,
    get_analysis,
    list_analyses,
    list_comments,
    list_feedback_examples,
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


def test_feedback_examples_are_exportable_for_retraining(tmp_path):
    db_path = tmp_path / "feedback.db"
    analysis_id, stored = save_analysis(
        source_type="youtube",
        source_text="원본 영상 설명",
        category="Entertainment",
        recommendations=[
            {"rank": 1, "type": "insight", "comment": "유용한 댓글", "predicted_score": 88.0},
            {"rank": 2, "type": "casual", "comment": "그저 그런 댓글", "predicted_score": 61.0},
            {"rank": 3, "type": "general", "comment": "평가 없는 댓글", "predicted_score": 55.0},
        ],
        youtube_context={"title": "영상 제목"},
        path=db_path,
    )

    set_feedback(stored[0]["id"], useful=True, path=db_path)
    set_feedback(stored[1]["id"], useful=False, path=db_path)

    examples = list_feedback_examples(path=db_path)

    # 평가가 없는 추천은 학습 데이터가 될 수 없으므로 제외된다.
    assert len(examples) == 2
    assert {row["label"] for row in examples} == {0, 1}
    assert all(row["analysis_id"] == analysis_id for row in examples)
    # video_title이 있으면 post_text로 쓰인다.
    assert all(row["post_text"] == "영상 제목" for row in examples)
