"""Minimal durable YouTube publication receipts.

Only identifiers and irrecoverable local prediction/measurement labels are kept.
Public YouTube counters and video details remain API-derived. This module is
server-only: DATABASE_URL must never be exposed in frontend bundles.
"""
from __future__ import annotations

import os


def durable_enabled() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


def persist_receipt(
    *, comment_id: str, video_id: str, owner_channel_id: str,
    recommendation_id: str | None = None, predicted_score: float | None = None,
    published_at: str | None = None,
) -> None:
    """Fail visibly when a configured durable store cannot accept the receipt."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return
    if not owner_channel_id:
        raise ValueError("A verified YouTube channel is required for durable storage")
    import psycopg
    with psycopg.connect(database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ai_comment_private.comment_receipts
                  (comment_id, owner_channel_id, video_id, recommendation_id,
                   predicted_score, published_at)
                  VALUES (%s,%s,%s,%s,%s,COALESCE(%s::timestamptz, now()))
                  ON CONFLICT (comment_id) DO UPDATE SET
                    owner_channel_id=EXCLUDED.owner_channel_id,
                    video_id=EXCLUDED.video_id,
                    recommendation_id=COALESCE(
                      ai_comment_private.comment_receipts.recommendation_id,
                      EXCLUDED.recommendation_id),
                    predicted_score=COALESCE(
                      ai_comment_private.comment_receipts.predicted_score,
                      EXCLUDED.predicted_score)
                  WHERE ai_comment_private.comment_receipts.owner_channel_id
                        = EXCLUDED.owner_channel_id""",
                (comment_id, owner_channel_id, video_id, recommendation_id,
                 predicted_score, published_at),
            )


def list_receipts(owner_channel_id: str, limit: int = 100) -> list[dict]:
    """Return only receipts belonging to the verified YouTube owner."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return []
    if not owner_channel_id:
        raise ValueError("Owner channel ID required")
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT comment_id, video_id, recommendation_id,
                          predicted_score, published_at, likes_24h,
                          replies_24h, likes_7d, replies_7d
                   FROM ai_comment_private.comment_receipts
                   WHERE owner_channel_id=%s
                   ORDER BY published_at DESC LIMIT %s""",
                (owner_channel_id, max(1, min(limit, 100))),
            )
            return list(cur.fetchall())
