from datetime import datetime, timezone

from src.storage.analysis_store import save_analysis, set_feedback
from src.storage.model_progress import model_data_progress


def test_model_data_progress_uses_only_real_stored_events(tmp_path):
    path = tmp_path / "progress.sqlite"
    now = datetime.now(timezone.utc)
    empty = model_data_progress(now=now, path=path)
    assert empty["observations"]["analyses"] == 0
    assert len(empty["daily"]) == 14
    assert empty["daily"][-1]["cumulative_analyses"] == 0
    assert empty["reference"]["usable_comments"] >= 0

    analysis_id, items = save_analysis(
        source_type="youtube",
        source_text="새 영상",
        category="vlog",
        recommendations=[
            {"rank": 1, "type": "insight", "comment": "정말 좋네요", "predicted_score": 57.0}
        ],
        youtube_context={"video_id": "dQw4w9WgXcQ", "title": "새 영상"},
        generation_context={
            "primary_category": "vlog",
            "historical_comments": {"matched_count": 8, "coverage": "matched_legacy_category"},
        },
        path=path,
    )
    assert analysis_id
    set_feedback(items[0]["id"], useful=True, path=path)

    result = model_data_progress(now=now, path=path)
    assert result["observations"]["analyses"] == 1
    assert result["observations"]["unique_videos"] == 1
    assert result["observations"]["stored_contexts"] == 1
    assert result["observations"]["recommendations"] == 1
    assert result["observations"]["feedback"] == 1
    assert result["observations"]["historical_matched_analyses"] == 1
    assert result["observations"]["average_matches"] == 8.0
    assert result["daily"][-1]["new_analyses"] == 1
    assert result["daily"][-1]["cumulative_analyses"] == 1
