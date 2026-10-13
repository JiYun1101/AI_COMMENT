"""Persist measured YouTube comment samples for per-video audience memory.

Save only the comment text and public engagement counts, not usernames or
OAuth credentials. Never accept a user-supplied JSON sample for storage.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from src.storage.analysis_store import _session, init_db


def _table(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audience_observation_snapshots (
            id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            analysis_id TEXT,
            observed_at TEXT NOT NULL,
            sample_count INTEGER NOT NULL,
            report_json TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_audience_observation_video_time
           ON audience_observation_snapshots(video_id, observed_at DESC)"""
    )


def save_audience_observation(report: dict, *, analysis_id: str | None = None, path=None) -> dict:
    init_db(path)
    recorded = datetime.now(timezone.utc).isoformat()
    snapshot_id = "obs_" + uuid.uuid4().hex[:16]
    with _session(path) as conn:
        _table(conn)
        conn.execute(
            """INSERT INTO audience_observation_snapshots
               (id, video_id, analysis_id, observed_at, sample_count, report_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (snapshot_id, report["video_id"], analysis_id, recorded,
             report["observed"]["total"], json.dumps(report, ensure_ascii=False)),
        )
    return {"id": snapshot_id, "video_id": report["video_id"],
            "analysis_id": analysis_id, "observed_at": recorded,
            "sample_count": report["observed"]["total"]}


def list_audience_observations(video_id: str, *, limit: int = 5, path=None) -> list[dict]:
    init_db(path)
    with _session(path) as conn:
        _table(conn)
        rows = conn.execute(
            """SELECT id, video_id, analysis_id, observed_at, sample_count
               FROM audience_observation_snapshots
               WHERE video_id = ? ORDER BY observed_at DESC LIMIT ?""",
            (video_id, max(1, min(limit, 20))),
        ).fetchall()
    return [dict(row) for row in rows]


def read_audience_observation(snapshot_id: str, *, path=None) -> dict | None:
    init_db(path)
    with _session(path) as conn:
        _table(conn)
        row = conn.execute(
            "SELECT id, observed_at, report_json FROM audience_observation_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "observed_at": row["observed_at"],
            "report": json.loads(row["report_json"])}
