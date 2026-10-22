"""Inspect real data flowing through the pre-LLM context builder.

Reference CSVs, inference/history records and feedback are deliberately kept
separate: observing new data does NOT retrain the fitted reaction ranker.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.recommender.historical_comments import DEFAULT_DATASET_PATHS, _load_dataset
from src.storage.analysis_store import _session, init_db


def model_data_progress(*, now=None, path=None) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date()
    reference_sources = [
        {"name": source.stem.replace("_comments", ""), "count": len(_load_dataset(str(source)))}
        for source in DEFAULT_DATASET_PATHS if source.is_file()
    ]

    init_db(path)
    with _session(path) as db:
        summary = db.execute(
            """SELECT COUNT(*) AS analyses,
                      COUNT(DISTINCT CASE WHEN video_id != '' THEN video_id END) AS videos,
                      COUNT(context_json) AS contexts
               FROM analyses"""
        ).fetchone()
        saved = db.execute(
            """SELECT COUNT(*) AS recommendations,
                      COUNT(feedback) AS feedback
               FROM recommendations"""
        ).fetchone()
        context_rows = db.execute(
            "SELECT context_json FROM analyses WHERE context_json IS NOT NULL"
        ).fetchall()
        date_rows = db.execute(
            """SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS total
               FROM analyses
               WHERE created_at >= ?
               GROUP BY substr(created_at, 1, 10)""",
            ((today - timedelta(days=13)).isoformat(),),
        ).fetchall()

    matched_analyses = 0
    total_matches = 0
    for row in context_rows:
        try:
            historical = (json.loads(row["context_json"]) or {}).get("historical_comments") or {}
            matched = max(0, int(historical.get("matched_count") or 0))
        except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
            continue
        if matched:
            matched_analyses += 1
            total_matches += matched

    totals_by_day = {row["day"]: row["total"] for row in date_rows}
    rolling_total = int(summary["analyses"]) - sum(totals_by_day.values())
    daily = []
    for index in range(13, -1, -1):
        day = (today - timedelta(days=index)).isoformat()
        added = int(totals_by_day.get(day, 0))
        rolling_total += added
        daily.append({"date": day, "new_analyses": added, "cumulative_analyses": rolling_total})

    return {
        "reference": {
            "usable_comments": sum(entry["count"] for entry in reference_sources),
            "sources": reference_sources,
            "meaning": "현재 서버에서 안전 필터를 통과해 검색에 사용할 수 있는 기존 댓글 자료",
        },
        "observations": {
            "analyses": int(summary["analyses"]),
            "unique_videos": int(summary["videos"]),
            "stored_contexts": int(summary["contexts"]),
            "recommendations": int(saved["recommendations"]),
            "feedback": int(saved["feedback"]),
            "historical_matched_analyses": matched_analyses,
            "average_matches": round(total_matches / matched_analyses, 1) if matched_analyses else None,
        },
        "daily": daily,
        "note": "분석 이력과 사용자 피드백은 축적되지만 반응 예측 모델을 자동으로 재학습하지 않습니다. 참조 댓글 수는 학습 완료 샘플 수와 다릅니다.",
    }
