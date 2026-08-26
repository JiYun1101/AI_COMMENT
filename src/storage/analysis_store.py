from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.config import BASE_DIR

DEFAULT_DB_PATH = BASE_DIR / "data" / "runtime" / "ai_comment.db"


def _db_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    configured = os.getenv("AI_COMMENT_DB_PATH")
    return Path(configured) if configured else DEFAULT_DB_PATH


def _connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = _db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_analysis_columns(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(analyses)").fetchall()}
    additions = {
        "context_json": "TEXT",
        "requested_count": "INTEGER",
        "additional_context": "TEXT",
    }
    for column, definition in additions.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE analyses ADD COLUMN {column} {definition}")


def init_db(path: str | Path | None = None) -> None:
    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_text TEXT NOT NULL,
                youtube_url TEXT,
                video_id TEXT,
                video_title TEXT,
                channel TEXT,
                thumbnail_url TEXT,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL,
                context_json TEXT,
                requested_count INTEGER,
                additional_context TEXT
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                rank INTEGER NOT NULL,
                type TEXT NOT NULL,
                comment TEXT NOT NULL,
                predicted_score REAL NOT NULL,
                feedback TEXT CHECK (feedback IN ('useful', 'not_useful') OR feedback IS NULL),
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_recommendations_analysis_id ON recommendations(analysis_id);
            CREATE INDEX IF NOT EXISTS idx_recommendations_score ON recommendations(predicted_score DESC);
            CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);
            """
        )
        _ensure_analysis_columns(connection)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _analysis_id() -> str:
    return f"a_{uuid.uuid4().hex[:12]}"


def _recommendation_id() -> str:
    return f"r_{uuid.uuid4().hex[:12]}"


def save_analysis(
    *,
    source_type: str,
    source_text: str,
    category: str,
    recommendations: Iterable[dict],
    youtube_context: dict | None = None,
    generation_context: dict | None = None,
    requested_count: int | None = None,
    additional_context: str | None = None,
    path: str | Path | None = None,
) -> tuple[str, list[dict]]:
    init_db(path)
    analysis_id = _analysis_id()
    created_at = _now_iso()
    youtube_context = youtube_context or {}
    context_json = json.dumps(generation_context, ensure_ascii=False) if generation_context else None

    stored_recommendations: list[dict] = []
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO analyses (
                id, source_type, source_text, youtube_url, video_id, video_title,
                channel, thumbnail_url, category, created_at, context_json,
                requested_count, additional_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                source_type,
                source_text,
                youtube_context.get("url"),
                youtube_context.get("video_id"),
                youtube_context.get("title"),
                youtube_context.get("channel"),
                youtube_context.get("thumbnail_url"),
                category,
                created_at,
                context_json,
                requested_count,
                additional_context,
            ),
        )

        for recommendation in recommendations:
            recommendation_id = _recommendation_id()
            stored = {**recommendation, "id": recommendation_id}
            stored_recommendations.append(stored)
            connection.execute(
                """
                INSERT INTO recommendations (
                    id, analysis_id, rank, type, comment, predicted_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation_id,
                    analysis_id,
                    int(recommendation["rank"]),
                    str(recommendation.get("type", "general")),
                    str(recommendation["comment"]),
                    float(recommendation["predicted_score"]),
                    created_at,
                ),
            )

    return analysis_id, stored_recommendations


def list_analyses(*, limit: int = 10, path: str | Path | None = None) -> list[dict]:
    init_db(path)
    with _connect(path) as connection:
        rows = connection.execute(
            """
            SELECT a.id, a.source_type, a.source_text, a.youtube_url, a.video_id,
                   a.video_title, a.channel, a.thumbnail_url, a.category, a.created_at,
                   a.requested_count, a.additional_context,
                   COUNT(r.id) AS recommendation_count,
                   COALESCE(AVG(r.predicted_score), 0) AS average_score
            FROM analyses a
            LEFT JOIN recommendations r ON r.analysis_id = a.id
            GROUP BY a.id
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_analysis(analysis_id: str, *, path: str | Path | None = None) -> dict | None:
    init_db(path)
    with _connect(path) as connection:
        analysis = connection.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        if analysis is None:
            return None
        recommendations = connection.execute(
            """
            SELECT id, rank, type, comment, predicted_score, feedback, created_at
            FROM recommendations
            WHERE analysis_id = ?
            ORDER BY rank ASC
            """,
            (analysis_id,),
        ).fetchall()

    result = dict(analysis)
    context_json = result.pop("context_json", None)
    if context_json:
        try:
            result["generation_context"] = json.loads(context_json)
        except json.JSONDecodeError:
            result["generation_context"] = None
    else:
        result["generation_context"] = None
    result["recommendations"] = [dict(row) for row in recommendations]
    return result


def list_comments(
    *,
    query: str | None = None,
    comment_type: str | None = None,
    category: str | None = None,
    min_score: float | None = None,
    limit: int = 50,
    offset: int = 0,
    path: str | Path | None = None,
) -> dict:
    init_db(path)
    where = []
    params: list[object] = []

    if query:
        where.append("(r.comment LIKE ? OR a.video_title LIKE ? OR a.source_text LIKE ?)")
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern])
    if comment_type:
        where.append("r.type = ?")
        params.append(comment_type)
    if category and category != "auto":
        where.append("LOWER(a.category) = LOWER(?)")
        params.append(category)
    if min_score is not None:
        where.append("r.predicted_score >= ?")
        params.append(min_score)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    base_from = f"FROM recommendations r JOIN analyses a ON a.id = r.analysis_id {where_sql}"

    with _connect(path) as connection:
        total = connection.execute(f"SELECT COUNT(*) {base_from}", params).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT r.id, r.analysis_id, r.rank, r.type, r.comment,
                   r.predicted_score, r.feedback, r.created_at,
                   a.category, a.source_type, a.video_title, a.channel
            {base_from}
            ORDER BY r.predicted_score DESC, r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    return {"total": int(total), "items": [dict(row) for row in rows]}


def dashboard_summary(*, path: str | Path | None = None) -> dict:
    init_db(path)
    with _connect(path) as connection:
        analysis_count = connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        recommendation_count = connection.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
        average_score = connection.execute("SELECT COALESCE(AVG(predicted_score), 0) FROM recommendations").fetchone()[0]
        useful = connection.execute("SELECT COUNT(*) FROM recommendations WHERE feedback = 'useful'").fetchone()[0]
        not_useful = connection.execute("SELECT COUNT(*) FROM recommendations WHERE feedback = 'not_useful'").fetchone()[0]

    feedback_total = useful + not_useful
    helpful_rate = round((useful / feedback_total) * 100, 1) if feedback_total else None
    return {
        "analysis_count": int(analysis_count),
        "recommendation_count": int(recommendation_count),
        "average_score": round(float(average_score), 2),
        "feedback_count": int(feedback_total),
        "helpful_rate": helpful_rate,
    }


def set_feedback(
    recommendation_id: str,
    *,
    useful: bool,
    path: str | Path | None = None,
) -> dict | None:
    init_db(path)
    feedback = "useful" if useful else "not_useful"
    with _connect(path) as connection:
        cursor = connection.execute(
            "UPDATE recommendations SET feedback = ? WHERE id = ?",
            (feedback, recommendation_id),
        )
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            "SELECT id, feedback FROM recommendations WHERE id = ?",
            (recommendation_id,),
        ).fetchone()
    return dict(row) if row else None
