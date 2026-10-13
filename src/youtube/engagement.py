"""공개 댓글의 실제 반응(좋아요·답글)과 영상 댓글 스레드를 API key로 읽어온다.

읽기 전용 조회라 OAuth 없이 YouTube Data API key만 사용한다.
"""

from __future__ import annotations

import requests

from src.youtube.context import VIDEO_ID_RE, YouTubeConfigurationError, YouTubeLookupError

YOUTUBE_COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
MAX_IDS_PER_REQUEST = 50


def _get(http, params: dict, api_key: str) -> requests.Response:
    try:
        return http.get(YOUTUBE_COMMENT_THREADS_URL, params={**params, "key": api_key}, timeout=10)
    except requests.RequestException as exc:
        raise YouTubeLookupError("YouTube API에 연결할 수 없습니다.") from exc


def _error_reason(response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    errors = ((body.get("error") or {}).get("errors") or []) if isinstance(body, dict) else []
    for item in errors:
        if isinstance(item, dict) and item.get("reason"):
            return str(item["reason"])
    return None


def _json_or_error(response, failure: str) -> dict:
    if response.status_code != 200:
        if _error_reason(response) == "commentsDisabled":
            raise YouTubeLookupError("이 영상은 댓글이 사용 중지되어 있습니다.")
        detail = (getattr(response, "text", "") or "")[:240]
        raise YouTubeLookupError(f"{failure} ({response.status_code}). {detail}".strip())
    try:
        return response.json()
    except ValueError as exc:
        raise YouTubeLookupError("YouTube API 응답을 해석할 수 없습니다.") from exc


def _require_key(api_key: str | None) -> str:
    key = (api_key or "").strip()
    if not key:
        raise YouTubeConfigurationError("YouTube API key가 필요합니다.")
    return key


def fetch_comment_metrics(comment_ids: list[str], *, api_key: str | None, session=None) -> dict[str, dict]:
    """최상위 댓글 ID별 현재 좋아요 수와 답글 수를 돌려준다.

    응답에 없는 ID는 삭제됐거나 검토 대기 중인 댓글이라 결과에서 빠진다.
    """
    key = _require_key(api_key)
    ids = [value for value in dict.fromkeys(comment_ids) if value]
    http = session or requests.Session()
    metrics: dict[str, dict] = {}
    for start in range(0, len(ids), MAX_IDS_PER_REQUEST):
        batch = ids[start : start + MAX_IDS_PER_REQUEST]
        body = _json_or_error(
            _get(http, {"part": "snippet", "id": ",".join(batch)}, key),
            "댓글 반응을 조회하지 못했습니다",
        )
        for item in body.get("items") or []:
            snippet = item.get("snippet") or {}
            top = (snippet.get("topLevelComment") or {}).get("snippet") or {}
            metrics[str(item.get("id"))] = {
                "like_count": int(top.get("likeCount") or 0),
                "reply_count": int(snippet.get("totalReplyCount") or 0),
            }
    return metrics


def fetch_video_comment_threads(
    video_id: str,
    *,
    api_key: str | None,
    order: str = "relevance",
    limit: int = 100,
    session=None,
) -> list[dict]:
    """영상의 최상위 댓글과 함께 내려오는 답글(최대 5개)을 정규화해 돌려준다."""
    if not VIDEO_ID_RE.fullmatch(video_id or ""):
        raise YouTubeLookupError("유효한 YouTube video_id가 아닙니다.")
    key = _require_key(api_key)
    http = session or requests.Session()
    threads: list[dict] = []
    page_token: str | None = None
    while len(threads) < limit:
        params = {
            "part": "snippet,replies",
            "videoId": video_id,
            "order": order if order in {"relevance", "time"} else "relevance",
            "maxResults": min(100, limit - len(threads)),
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        body = _json_or_error(_get(http, params, key), "영상 댓글을 불러오지 못했습니다")
        for item in body.get("items") or []:
            snippet = item.get("snippet") or {}
            top = (snippet.get("topLevelComment") or {}).get("snippet") or {}
            replies = [
                {
                    "author_channel_id": ((reply.get("snippet") or {}).get("authorChannelId") or {}).get("value"),
                    "text": (reply.get("snippet") or {}).get("textOriginal")
                    or (reply.get("snippet") or {}).get("textDisplay")
                    or "",
                }
                for reply in (item.get("replies") or {}).get("comments") or []
            ]
            threads.append(
                {
                    "id": str(item.get("id")),
                    "author": top.get("authorDisplayName") or "",
                    "author_channel_id": (top.get("authorChannelId") or {}).get("value"),
                    "text": top.get("textOriginal") or top.get("textDisplay") or "",
                    "like_count": int(top.get("likeCount") or 0),
                    "reply_count": int(snippet.get("totalReplyCount") or 0),
                    "published_at": top.get("publishedAt"),
                    "can_reply": bool(snippet.get("canReply", True)),
                    "replies": replies,
                }
            )
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    return threads[:limit]
