"""Channel-scoped, idempotent snapshots of YouTube video counters.

Cumulative YouTube Data API counters are not YouTube Analytics daily metrics.
A 24h/7d difference is shown only when a recorded baseline exists.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from src.storage.analysis_store import _session, init_db

REFRESH_COOLDOWN = timedelta(minutes=5)
SNAPSHOT_SPACING = timedelta(hours=1)
SNAPSHOT_RETENTION = timedelta(days=45)


def _now():
    return datetime.now(timezone.utc)


def _schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS owned_videos (
        owner_channel_id TEXT NOT NULL,
        video_id TEXT NOT NULL,
        title TEXT NOT NULL,
        thumbnail_url TEXT,
        published_at TEXT,
        privacy_status TEXT NOT NULL,
        views INTEGER,
        likes INTEGER,
        comments INTEGER,
        last_checked_at TEXT NOT NULL,
        PRIMARY KEY (owner_channel_id, video_id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS owned_video_snapshots (
        owner_channel_id TEXT NOT NULL,
        video_id TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        views INTEGER,
        likes INTEGER,
        comments INTEGER,
        PRIMARY KEY (owner_channel_id, video_id, observed_at)
    )""")
    db.execute("""CREATE INDEX IF NOT EXISTS idx_owned_video_snapshots_history
        ON owned_video_snapshots(owner_channel_id, video_id, observed_at DESC)""")
    db.execute("""CREATE TABLE IF NOT EXISTS owned_video_sync (
        owner_channel_id TEXT PRIMARY KEY,
        channel_title TEXT NOT NULL,
        last_sync_at TEXT NOT NULL
    )""")


def last_sync(channel_id: str, *, path=None):
    init_db(path)
    with _session(path) as db:
        _schema(db)
        row = db.execute("SELECT last_sync_at FROM owned_video_sync WHERE owner_channel_id = ?",
                         (channel_id,)).fetchone()
    return datetime.fromisoformat(row[0]) if row else None


def recently_synced(channel_id: str, *, now=None, path=None) -> bool:
    time = last_sync(channel_id, path=path)
    return bool(time and (now or _now()) - time < REFRESH_COOLDOWN)


def save_video_metrics(channel_id: str, channel_title: str, videos: list[dict], *,
                       observed_at=None, mark_sync=True, path=None) -> int:
    if not channel_id:
        raise ValueError("Verified channel ID is required")
    now = observed_at or _now()
    stamp = now.isoformat()
    init_db(path)
    written = 0
    with _session(path) as db:
        _schema(db)
        for video in videos:
            vid = video.get("video_id")
            if not isinstance(vid, str) or len(vid) != 11:
                continue
            db.execute(
                """INSERT INTO owned_videos
                  (owner_channel_id, video_id, title, thumbnail_url, published_at,
                   privacy_status, views, likes, comments, last_checked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(owner_channel_id, video_id) DO UPDATE SET
                   title=excluded.title, thumbnail_url=excluded.thumbnail_url,
                   published_at=excluded.published_at, privacy_status=excluded.privacy_status,
                   views=excluded.views, likes=excluded.likes,
                   comments=excluded.comments, last_checked_at=excluded.last_checked_at""",
                (channel_id, vid, video["title"], video.get("thumbnail_url"),
                 video.get("published_at"), video.get("privacy_status") or "unknown",
                 video.get("views"), video.get("likes"), video.get("comments"), stamp),
            )
            last = db.execute(
                """SELECT observed_at FROM owned_video_snapshots
                   WHERE owner_channel_id = ? AND video_id = ?
                   ORDER BY observed_at DESC LIMIT 1""", (channel_id, vid),
            ).fetchone()
            if not last or now - datetime.fromisoformat(last[0]) >= SNAPSHOT_SPACING:
                db.execute(
                    """INSERT INTO owned_video_snapshots
                      (owner_channel_id, video_id, observed_at, views, likes, comments)
                      VALUES (?, ?, ?, ?, ?, ?)""",
                    (channel_id, vid, stamp, video.get("views"), video.get("likes"),
                     video.get("comments")),
                )
            written += 1
        # Limit the size of the video metrics table on long-running servers.
        # Keep enough hourly samples for 7-day comparisons with margin.
        db.execute(
            "DELETE FROM owned_video_snapshots WHERE owner_channel_id = ? AND observed_at < ?",
            (channel_id, (now - SNAPSHOT_RETENTION).isoformat()),
        )
        if mark_sync:
            db.execute(
                """INSERT INTO owned_video_sync(owner_channel_id, channel_title, last_sync_at)
                   VALUES (?, ?, ?) ON CONFLICT(owner_channel_id) DO UPDATE SET
                   channel_title=excluded.channel_title,last_sync_at=excluded.last_sync_at""",
                (channel_id, channel_title, stamp),
            )
    return written


def _delta(current, baseline):
    if current is None or baseline is None:
        return None
    # A counter can decrease when YouTube removes invalid activity.
    return current - baseline


def list_video_metrics(channel_id: str, *, now=None, limit=300, path=None) -> dict:
    now = now or _now()
    init_db(path)
    with _session(path) as db:
        _schema(db)
        state = db.execute(
            "SELECT channel_title,last_sync_at FROM owned_video_sync WHERE owner_channel_id = ?",
            (channel_id,),
        ).fetchone()
        rows = db.execute(
            """SELECT * FROM owned_videos WHERE owner_channel_id = ?
               ORDER BY published_at DESC, video_id DESC LIMIT ?""",
            (channel_id, max(1, min(limit, 500))),
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            snapshots = db.execute(
                """SELECT observed_at,views,likes,comments
                   FROM owned_video_snapshots WHERE owner_channel_id = ? AND video_id = ?
                   ORDER BY observed_at DESC LIMIT 300""",
                (channel_id, item["video_id"]),
            ).fetchall()
            if snapshots:
                previous = snapshots[1] if len(snapshots) >= 2 else None
                item["views_since_previous"] = _delta(item["views"], previous["views"] if previous else None)
                for label, period, tolerance in (
                    ("24h", timedelta(hours=24), timedelta(hours=6)),
                    ("7d", timedelta(days=7), timedelta(days=1)),
                ):
                    target = now - period
                    # Nearest observation in an explicit window, never pretend an
                    # arbitrary old first snapshot is an exact 24-hour sample.
                    candidates = [
                        s for s in snapshots
                        if abs(datetime.fromisoformat(s["observed_at"]) - target) <= tolerance
                    ]
                    baseline = min(
                        candidates,
                        key=lambda s: abs(datetime.fromisoformat(s["observed_at"]) - target),
                    ) if candidates else None
                    item["views_" + label] = _delta(
                        item["views"], baseline["views"] if baseline else None,
                    )
            else:
                item.update(views_since_previous=None, views_24h=None, views_7d=None)
            items.append(item)
    visible = [x for x in items if x["views"] is not None]
    views_sum = sum(x["views"] for x in visible)
    return {
        "channel_id": channel_id,
        "channel_title": state["channel_title"] if state else "",
        "last_sync_at": state["last_sync_at"] if state else None,
        "storage_persistent": False,  # overridden by API using verified deployment flag
        "summary": {
            "tracked_count": len(items),
            "measured_count": len(visible),
            "total_views": views_sum,
            "total_likes": sum(x["likes"] for x in items if x["likes"] is not None),
            "total_comments": sum(x["comments"] for x in items if x["comments"] is not None),
            "average_views": round(views_sum / len(visible), 1) if visible else None,
        },
        "items": items,
    }
