"""Read authenticated channel uploads and per-video public counters.

Only the OAuth-authenticated channel is queried. Do not accept an arbitrary
channel ID from the browser or silently treat absent counters as zero.
"""
from __future__ import annotations

import requests

from src.youtube.comments import (
    _authorized_json,
    YouTubeCommentPublishError,
)

API = "https://www.googleapis.com/youtube/v3"


def _int_or_none(value):
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _oauth(**kwargs):
    return {
        "client_id": kwargs.get("client_id"),
        "client_secret": kwargs.get("client_secret"),
        "redirect_uri": kwargs.get("redirect_uri"),
    }


def _channel(http, options):
    response = _authorized_json(
        http, API + "/channels",
        params={"part": "id,snippet,contentDetails", "mine": "true"},
        failure="내 YouTube 채널 정보를 읽지 못했습니다", **options,
    )
    channels = response.get("items") or []
    if not channels or not channels[0].get("id"):
        raise YouTubeCommentPublishError(
            "연결된 Google 계정에 YouTube 채널이 없습니다. 채널을 만든 뒤 다시 연결해주세요.",
            status_code=403,
        )
    ch = channels[0]
    return {
        "channel_id": str(ch["id"]),
        "channel_title": str((ch.get("snippet") or {}).get("title") or ""),
        "uploads_playlist": str(
            ((ch.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads") or ""
        ),
    }


def _parse_video(item, owner_id: str):
    snippet = item.get("snippet") or {}
    if snippet.get("channelId") != owner_id:
        return None
    vid = str(item.get("id") or "")
    if not vid or len(vid) != 11:
        return None
    stats = item.get("statistics") or {}
    thumbs = snippet.get("thumbnails") or {}
    thumb = next(
        (thumbs.get(name, {}).get("url") for name in ("medium", "high", "default")
         if isinstance(thumbs.get(name), dict) and thumbs[name].get("url")),
        None,
    )
    return {
        "video_id": vid,
        "title": str(snippet.get("title") or "제목 없는 영상")[:300],
        "thumbnail_url": thumb,
        "published_at": snippet.get("publishedAt"),
        "privacy_status": (item.get("status") or {}).get("privacyStatus") or "unknown",
        "views": _int_or_none(stats.get("viewCount")),
        "likes": _int_or_none(stats.get("likeCount")),
        "comments": _int_or_none(stats.get("commentCount")),
    }


def fetch_my_videos(*, limit: int = 100, session=None,
                    client_id=None, client_secret=None, redirect_uri=None) -> dict:
    """channels.list + uploads playlistItems.list + batched videos.list.

    1-2 playlist pages and 1-2 video batches for 100 videos. No search.list.
    """
    if not 1 <= limit <= 200:
        raise ValueError("한 번에 1~200개의 영상을 조회할 수 있습니다.")
    http = session or requests.Session()
    options = _oauth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    channel = _channel(http, options)
    playlist = channel["uploads_playlist"]
    if not playlist:
        raise YouTubeCommentPublishError("채널 업로드 영상 목록을 찾지 못했습니다.", status_code=404)
    ids = []
    token = None
    pages = 0
    while len(ids) < limit and pages < 4:
        params = {"part": "contentDetails", "playlistId": playlist,
                  "maxResults": min(50, limit - len(ids))}
        if token:
            params["pageToken"] = token
        response = _authorized_json(
            http, API + "/playlistItems", params=params,
            failure="내 업로드 영상 목록을 읽지 못했습니다", **options,
        )
        for row in response.get("items") or []:
            vid = str((row.get("contentDetails") or {}).get("videoId") or "")
            if len(vid) == 11 and vid not in ids:
                ids.append(vid)
        pages += 1
        token = response.get("nextPageToken")
        if not token:
            break

    videos = {}
    for start in range(0, len(ids), 50):
        response = _authorized_json(
            http, API + "/videos",
            params={"part": "snippet,statistics,status", "id": ",".join(ids[start:start + 50])},
            failure="영상별 실제 성과를 조회하지 못했습니다", **options,
        )
        for item in response.get("items") or []:
            video = _parse_video(item, channel["channel_id"])
            if video:
                videos[video["video_id"]] = video
    return {
        "channel_id": channel["channel_id"],
        "channel_title": channel["channel_title"],
        "videos": [videos[vid] for vid in ids if vid in videos],
        "limit_reached": len(ids) >= limit and bool(token),
    }


def fetch_owned_video(video_id: str, *, session=None,
                      client_id=None, client_secret=None, redirect_uri=None) -> dict:
    """Register an older upload outside the recent uploads page by verified owner."""
    from src.youtube.context import VIDEO_ID_RE
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise YouTubeCommentPublishError("YouTube 영상 ID가 올바르지 않습니다.", status_code=422)
    http = session or requests.Session()
    options = _oauth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    channel = _channel(http, options)
    response = _authorized_json(
        http, API + "/videos",
        params={"part": "snippet,statistics,status", "id": video_id},
        failure="영상 성과를 조회하지 못했습니다", **options,
    )
    videos = [
        _parse_video(item, channel["channel_id"])
        for item in response.get("items") or []
    ]
    owned = next((item for item in videos if item), None)
    if not owned:
        raise YouTubeCommentPublishError(
            "현재 연결된 YouTube 채널이 업로드한 영상만 추적할 수 있습니다.",
            status_code=403,
        )
    return {"channel_id": channel["channel_id"],
            "channel_title": channel["channel_title"], "videos": [owned]}
