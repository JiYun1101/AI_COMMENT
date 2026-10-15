"""앱에서 YouTube에 게시한 댓글과 그 뒤의 실제 반응을 기록한다.

추천 단계의 예측 점수(predicted_score)와 게시 후 실제 좋아요·답글을 한 행에 모아
"예측이 실제로 맞았는가"를 확인하고, 이후 랭커 재학습용 라벨로 쓸 수 있게 한다.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.storage.analysis_store import _connect, init_db
from src.storage.durable_receipts import persist_receipt

logger = logging.getLogger(__name__)

MILESTONES = (("24h", timedelta(hours=24)), ("7d", timedelta(days=7)))


def init_published_db(path: str | Path | None = None) -> None:
    init_db(path)
    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS published_comments (
                id TEXT PRIMARY KEY,
                recommendation_id TEXT REFERENCES recommendations(id) ON DELETE SET NULL,
                account_mode TEXT NOT NULL,
                owner_channel_id TEXT,
                video_id TEXT NOT NULL,
                comment_id TEXT NOT NULL UNIQUE,
                comment TEXT NOT NULL,
                comment_url TEXT,
                published_at TEXT NOT NULL,
                like_count INTEGER,
                reply_count INTEGER,
                likes_24h INTEGER,
                replies_24h INTEGER,
                likes_7d INTEGER,
                replies_7d INTEGER,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'active', 'missing')),
                last_checked_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_published_comments_published_at
                ON published_comments(published_at DESC);
            """
        )

    # Legacy rows are unscoped until the original author is re-verified.
    with _connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(published_comments)")}
        if "owner_channel_id" not in columns:
            connection.execute("ALTER TABLE published_comments ADD COLUMN owner_channel_id TEXT")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_published_owner ON published_comments(owner_channel_id, published_at DESC)"
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_published_comment(
    *,
    video_id: str,
    comment_id: str,
    comment: str,
    comment_url: str | None,
    account_mode: str,
    recommendation_id: str | None = None,
    owner_channel_id: str | None = None,
    published_at: str | None = None,
    path: str | Path | None = None,
) -> str:
    init_published_db(path)
    published_id = f"p_{uuid.uuid4().hex[:12]}"
    with _connect(path) as connection:
        if recommendation_id:
            exists = connection.execute(
                "SELECT 1 FROM recommendations WHERE id = ?", (recommendation_id,)
            ).fetchone()
            if exists is None:
                recommendation_id = None
        connection.execute(
            """
            INSERT OR IGNORE INTO published_comments (
                id, recommendation_id, account_mode, owner_channel_id, video_id, comment_id,
                comment, comment_url, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                published_id,
                recommendation_id,
                account_mode,
                owner_channel_id,
                video_id,
                comment_id,
                comment,
                comment_url,
                published_at or _now().isoformat(),
            ),
        )
        if owner_channel_id:
            connection.execute(
                """UPDATE published_comments SET owner_channel_id = ?
                   WHERE comment_id = ? AND owner_channel_id IS NULL""",
                (owner_channel_id, comment_id),
            )
        row = connection.execute(
            "SELECT id FROM published_comments WHERE comment_id = ?", (comment_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("게시 기록을 저장하지 못했습니다.")
        saved_id = str(row["id"])
        prediction = None
        if recommendation_id:
            score = connection.execute(
                "SELECT predicted_score FROM recommendations WHERE id = ?",
                (recommendation_id,),
            ).fetchone()
            prediction = float(score[0]) if score is not None else None
    # YouTube has already accepted the comment. Do not raise here: a retry
    # could publish a duplicate. Log durable-storage failure for recovery.
    if owner_channel_id and account_mode == "personal":
        try:
            persist_receipt(
                comment_id=comment_id, video_id=video_id,
                owner_channel_id=owner_channel_id,
                recommendation_id=recommendation_id,
                predicted_score=prediction, published_at=published_at,
            )
        except Exception:
            logger.exception("Durable receipt failed for published comment")
    return saved_id


def update_owned_published_text(comment_id: str, owner_channel_id: str, text: str,
                                *, path: str | Path | None = None) -> bool:
    """Update only the verified owner's tracking row after YouTube succeeds."""
    init_published_db(path)
    with _connect(path) as connection:
        cursor = connection.execute(
            """UPDATE published_comments SET comment = ?
               WHERE comment_id = ? AND account_mode = 'personal'
                 AND owner_channel_id = ?""",
            (text, comment_id, owner_channel_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def delete_owned_published_record(comment_id: str, owner_channel_id: str,
                                  *, path: str | Path | None = None) -> bool:
    """Remove only the verified owner's tracking row after YouTube deletion."""
    init_published_db(path)
    with _connect(path) as connection:
        cursor = connection.execute(
            """DELETE FROM published_comments
               WHERE comment_id = ? AND account_mode = 'personal'
                 AND owner_channel_id = ?""",
            (comment_id, owner_channel_id),
        )
        connection.commit()
        return cursor.rowcount > 0


_SELECT = """
    SELECT p.*, r.predicted_score, r.type AS comment_type, a.video_title, a.channel
    FROM published_comments p
    LEFT JOIN recommendations r ON r.id = p.recommendation_id
    LEFT JOIN analyses a ON a.id = r.analysis_id
"""


def _with_age(row: dict, now: datetime) -> dict:
    published = datetime.fromisoformat(row["published_at"])
    row["hours_since_publish"] = round((now - published).total_seconds() / 3600, 1)
    return row


def list_published_comments(
    *,
    account_mode: str | None = None,
    owner_channel_id: str | None = None,
    limit: int = 100,
    path: str | Path | None = None,
) -> list[dict]:
    init_published_db(path)
    conditions, params = [], []
    if account_mode:
        conditions.append("p.account_mode = ?")
        params.append(account_mode)
    if owner_channel_id:
        conditions.append("p.owner_channel_id = ?")
        params.append(owner_channel_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with _connect(path) as connection:
        rows = connection.execute(
            f"{_SELECT} {where} ORDER BY p.published_at DESC LIMIT ?",
            [*params, limit],
        ).fetchall()
    now = _now()
    return [_with_age(dict(row), now) for row in rows]


def comment_ids_to_refresh(
    *,
    account_mode: str | None = None,
    owner_channel_id: str | None = None,
    min_interval_minutes: int = 10,
    path: str | Path | None = None,
) -> list[str]:
    """최근에 확인하지 않은 댓글만 골라 YouTube API 할당량을 아낀다."""
    init_published_db(path)
    cutoff = (_now() - timedelta(minutes=min_interval_minutes)).isoformat()
    where = ["(last_checked_at IS NULL OR last_checked_at < ?)"]
    params: list[object] = [cutoff]
    if account_mode:
        where.append("account_mode = ?")
        params.append(account_mode)
    if owner_channel_id:
        where.append("owner_channel_id = ?")
        params.append(owner_channel_id)
    with _connect(path) as connection:
        rows = connection.execute(
            f"SELECT comment_id FROM published_comments WHERE {' AND '.join(where)}",
            params,
        ).fetchall()
    return [row["comment_id"] for row in rows]


def apply_comment_metrics(
    comment_ids: list[str],
    metrics: dict[str, dict],
    *,
    now: datetime | None = None,
    path: str | Path | None = None,
) -> int:
    """조회한 반응을 저장한다. 응답에 없는 댓글은 삭제/검토 대기로 보고 missing 처리한다.

    24시간·7일 값은 해당 시점이 지난 뒤 처음 확인한 값으로 한 번만 고정한다.
    """
    init_published_db(path)
    checked_at = now or _now()
    updated = 0
    with _connect(path) as connection:
        for comment_id in comment_ids:
            row = connection.execute(
                "SELECT published_at, likes_24h, likes_7d FROM published_comments WHERE comment_id = ?",
                (comment_id,),
            ).fetchone()
            if row is None:
                continue
            values = metrics.get(comment_id)
            if values is None:
                connection.execute(
                    "UPDATE published_comments SET status = 'missing', last_checked_at = ? WHERE comment_id = ?",
                    (checked_at.isoformat(), comment_id),
                )
                updated += 1
                continue

            assignments = {
                "like_count": values["like_count"],
                "reply_count": values["reply_count"],
                "status": "active",
                "last_checked_at": checked_at.isoformat(),
            }
            elapsed = checked_at - datetime.fromisoformat(row["published_at"])
            for label, threshold in MILESTONES:
                if elapsed >= threshold and row[f"likes_{label}"] is None:
                    assignments[f"likes_{label}"] = values["like_count"]
                    assignments[f"replies_{label}"] = values["reply_count"]
            columns = ", ".join(f"{name} = ?" for name in assignments)
            connection.execute(
                f"UPDATE published_comments SET {columns} WHERE comment_id = ?",
                [*assignments.values(), comment_id],
            )
            updated += 1
    return updated


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2 + 1
        for index in order[position : end + 1]:
            ranks[index] = average
        position = end + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """동순위 평균 처리한 스피어만 순위 상관계수. 표본이 3개 미만이거나 분산이 없으면 None."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = _average_ranks(xs), _average_ranks(ys)
    mean_x, mean_y = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return None
    return round(cov / (var_x * var_y) ** 0.5, 3)


def published_summary(items: list[dict]) -> dict:
    measured = [item for item in items if item["status"] == "active" and item["like_count"] is not None]
    paired = [item for item in measured if item["predicted_score"] is not None]

    by_type: dict[str, list[int]] = {}
    for item in measured:
        by_type.setdefault(item["comment_type"] or "manual", []).append(item["like_count"])

    def average(values: list[int]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    return {
        "tracked_count": len(items),
        "measured_count": len(measured),
        "missing_count": sum(1 for item in items if item["status"] == "missing"),
        "average_likes": average([item["like_count"] for item in measured]),
        "replied_rate": (
            round(sum(1 for item in measured if item["reply_count"]) / len(measured) * 100, 1)
            if measured
            else None
        ),
        "prediction_pair_count": len(paired),
        "prediction_spearman": spearman(
            [item["predicted_score"] for item in paired],
            [float(item["like_count"]) for item in paired],
        ),
        "by_type": [
            {"type": key, "count": len(values), "average_likes": average(values)}
            for key, values in sorted(by_type.items(), key=lambda pair: -len(pair[1]))
        ],
    }


def list_legacy_unbound_comments(*, limit: int = 30, path: str | Path | None = None) -> list[dict]:
    """Legacy personal rows have no author ID. Never show them to a new channel."""
    init_published_db(path)
    with _connect(path) as connection:
        rows = connection.execute(
            """SELECT comment_id, video_id FROM published_comments
               WHERE account_mode = 'personal' AND owner_channel_id IS NULL
               ORDER BY published_at DESC LIMIT ?""", (max(1, min(limit, 100)),)
        ).fetchall()
    return [dict(row) for row in rows]


def attach_verified_legacy_comment(
    comment_id: str, channel_id: str, *, path: str | Path | None = None,
) -> bool:
    """Only called after verified YouTube API proves the channel authored comment_id."""
    init_published_db(path)
    with _connect(path) as conn:
        cursor = conn.execute(
            """UPDATE published_comments SET owner_channel_id = ?
               WHERE comment_id = ? AND account_mode = 'personal'
                 AND owner_channel_id IS NULL""", (channel_id, comment_id),
        )
        return cursor.rowcount == 1
