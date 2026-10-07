from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque

import requests

from src.youtube.comments import YouTubeCommentPublishError
from src.youtube.context import VIDEO_ID_RE

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

_RATE_LOCK = threading.Lock()
_VISITOR_EVENTS: dict[str, deque[float]] = defaultdict(deque)
_GLOBAL_EVENTS: deque[float] = deque()


class DemoYouTubeNotConfiguredError(RuntimeError):
    pass


class DemoYouTubeRateLimitError(RuntimeError):
    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int((os.getenv(name) or "").strip() or default)
    except ValueError:
        return default
    return max(1, value)


def _demo_config() -> tuple[str, str, str]:
    client_id = (os.getenv("DEMO_YOUTUBE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("DEMO_YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip()
    refresh_token = (os.getenv("DEMO_YOUTUBE_OAUTH_REFRESH_TOKEN") or "").strip()
    if not client_id or not client_secret or not refresh_token:
        raise DemoYouTubeNotConfiguredError(
            "데모 YouTube 채널이 아직 연결되지 않았습니다. "
            "운영자가 테스트 채널 OAuth 설정을 완료한 뒤 다시 시도해주세요."
        )
    return client_id, client_secret, refresh_token


def demo_visitor_key(raw_identity: str) -> str:
    normalized = (raw_identity or "anonymous").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _trim_events(now: float, visitor_key: str) -> tuple[deque[float], deque[float]]:
    visitor = _VISITOR_EVENTS[visitor_key]
    hourly_cutoff = now - 60 * 60
    daily_cutoff = now - 24 * 60 * 60

    while visitor and visitor[0] <= hourly_cutoff:
        visitor.popleft()
    while _GLOBAL_EVENTS and _GLOBAL_EVENTS[0] <= daily_cutoff:
        _GLOBAL_EVENTS.popleft()
    return visitor, _GLOBAL_EVENTS


def demo_status(visitor_key: str | None = None) -> dict:
    youtube_api_configured = bool((os.getenv("DEMO_YOUTUBE_API_KEY") or "").strip())
    openai_configured = bool((os.getenv("DEMO_OPENAI_API_KEY") or "").strip()) and bool(
        (os.getenv("DEMO_OPENAI_MODEL") or "").strip()
    )
    posting_configured = all(
        bool((os.getenv(name) or "").strip())
        for name in (
            "DEMO_YOUTUBE_OAUTH_CLIENT_ID",
            "DEMO_YOUTUBE_OAUTH_CLIENT_SECRET",
            "DEMO_YOUTUBE_OAUTH_REFRESH_TOKEN",
        )
    )
    configured = youtube_api_configured and openai_configured and posting_configured
    hourly_limit = _positive_int_env("DEMO_YOUTUBE_HOURLY_LIMIT", 3)
    daily_limit = _positive_int_env("DEMO_YOUTUBE_DAILY_LIMIT", 30)

    remaining_hourly = hourly_limit
    remaining_daily = daily_limit
    if visitor_key:
        now = time.time()
        with _RATE_LOCK:
            visitor, global_events = _trim_events(now, visitor_key)
            remaining_hourly = max(0, hourly_limit - len(visitor))
            remaining_daily = max(0, daily_limit - len(global_events))

    return {
        "configured": configured,
        "ready": configured,
        "youtube_api_configured": youtube_api_configured,
        "openai_configured": openai_configured,
        "posting_configured": posting_configured,
        "hourly_limit": hourly_limit,
        "daily_limit": daily_limit,
        "remaining_hourly": remaining_hourly,
        "remaining_daily": remaining_daily,
    }


def _consume_publish_slot(visitor_key: str) -> None:
    now = time.time()
    hourly_limit = _positive_int_env("DEMO_YOUTUBE_HOURLY_LIMIT", 3)
    daily_limit = _positive_int_env("DEMO_YOUTUBE_DAILY_LIMIT", 30)

    with _RATE_LOCK:
        visitor, global_events = _trim_events(now, visitor_key)

        if len(visitor) >= hourly_limit:
            retry_after = max(1, int(visitor[0] + 60 * 60 - now))
            raise DemoYouTubeRateLimitError(
                f"데모 계정은 방문자당 1시간에 {hourly_limit}회까지 게시할 수 있습니다.",
                retry_after_seconds=retry_after,
            )

        if len(global_events) >= daily_limit:
            retry_after = max(1, int(global_events[0] + 24 * 60 * 60 - now))
            raise DemoYouTubeRateLimitError(
                f"데모 계정의 오늘 전체 게시 한도({daily_limit}회)를 모두 사용했습니다.",
                retry_after_seconds=retry_after,
            )

        visitor.append(now)
        global_events.append(now)


def _refresh_demo_access_token(*, session=None) -> str:
    client_id, client_secret, refresh_token = _demo_config()
    http = session or requests.Session()
    try:
        response = http.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise YouTubeCommentPublishError(
            "데모 YouTube 계정의 OAuth 토큰을 갱신할 수 없습니다.",
            status_code=502,
        ) from exc

    if response.status_code < 200 or response.status_code >= 300:
        detail = (getattr(response, "text", "") or "")[:300]
        raise YouTubeCommentPublishError(
            f"데모 YouTube 계정 인증에 실패했습니다 ({response.status_code}). {detail}".strip(),
            status_code=502,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise YouTubeCommentPublishError(
            "데모 YouTube OAuth 응답을 해석할 수 없습니다.",
            status_code=502,
        ) from exc

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise YouTubeCommentPublishError(
            "데모 YouTube OAuth 응답에 access token이 없습니다.",
            status_code=502,
        )
    return access_token


def _youtube_error_reason(response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    errors = ((body.get("error") or {}).get("errors") or []) if isinstance(body, dict) else []
    for item in errors:
        if isinstance(item, dict) and item.get("reason"):
            return str(item["reason"])
    return None


def publish_demo_youtube_comment(
    *,
    video_id: str,
    channel_id: str,
    comment: str,
    visitor_key: str,
    session=None,
) -> dict:
    video_id = video_id.strip()
    channel_id = channel_id.strip()
    comment = comment.strip()

    if not VIDEO_ID_RE.fullmatch(video_id):
        raise YouTubeCommentPublishError("유효한 YouTube video_id가 아닙니다.", status_code=400)
    if not channel_id:
        raise YouTubeCommentPublishError("YouTube channel_id가 필요합니다.", status_code=400)
    if not comment:
        raise YouTubeCommentPublishError("게시할 댓글이 비어 있습니다.", status_code=400)
    if len(comment) > 10_000:
        raise YouTubeCommentPublishError("YouTube 댓글이 너무 깁니다.", status_code=400)

    _demo_config()
    _consume_publish_slot(visitor_key)

    http = session or requests.Session()
    access_token = _refresh_demo_access_token(session=http)

    payload = {
        "snippet": {
            "channelId": channel_id,
            "videoId": video_id,
            "topLevelComment": {
                "snippet": {
                    "textOriginal": comment,
                }
            },
        }
    }

    try:
        response = http.post(
            YOUTUBE_COMMENT_THREADS_URL,
            params={"part": "snippet"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise YouTubeCommentPublishError("YouTube 댓글 API에 연결할 수 없습니다.") from exc

    if response.status_code < 200 or response.status_code >= 300:
        reason = _youtube_error_reason(response)
        if response.status_code == 403 and reason == "ineligibleAccount":
            raise YouTubeCommentPublishError(
                "현재 데모 Google 계정에는 댓글을 작성할 수 있는 YouTube 채널이 없습니다. "
                "운영자가 테스트 채널을 연결해야 합니다.",
                status_code=403,
            )
        detail = (getattr(response, "text", "") or "")[:500]
        mapped = response.status_code if response.status_code in {400, 401, 403, 404} else 502
        raise YouTubeCommentPublishError(
            f"YouTube 댓글 게시에 실패했습니다 ({response.status_code}). {detail}".strip(),
            status_code=mapped,
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise YouTubeCommentPublishError("YouTube 댓글 게시 응답을 해석할 수 없습니다.") from exc

    top_level = ((body.get("snippet") or {}).get("topLevelComment") or {})
    comment_id = top_level.get("id") or body.get("id")
    return {
        "posted": True,
        "account_mode": "demo",
        "video_id": video_id,
        "comment_id": comment_id,
        "comment": comment,
        "comment_url": (
            f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"
            if comment_id
            else f"https://www.youtube.com/watch?v={video_id}"
        ),
    }
