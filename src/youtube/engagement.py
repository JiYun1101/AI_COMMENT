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
    """Return current likes/replies by actual comment ID (read-only Data API).

    Unlike commentThreads, comments.list(id=...) can also retrieve replies.
    For a top-level comment, comments.list(parentId=...) returns reply count.
    """
    key = _require_key(api_key)
    ids = [value for value in dict.fromkeys(comment_ids) if value]
    http = session or requests.Session()
    metrics: dict[str, dict] = {}
    for start in range(0, len(ids), MAX_IDS_PER_REQUEST):
        batch = ids[start : start + MAX_IDS_PER_REQUEST]
        body = _json_or_error(
            http.get(
                "https://www.googleapis.com/youtube/v3/comments",
                params={"part": "snippet", "id": ",".join(batch), "key": key},
                timeout=10,
            ),
            "댓글 반응을 조회하지 못했습니다",
        )
        for item in body.get("items") or []:
            cid = str(item.get("id") or "")
            if cid not in batch:
                continue
            snippet = item.get("snippet") or {}
            replies = 0
            if not snippet.get("parentId"):
                reply_data = _json_or_error(
                    http.get(
                        "https://www.googleapis.com/youtube/v3/comments",
                        params={"part": "snippet", "parentId": cid,
                                "maxResults": 100, "key": key},
                        timeout=10,
                    ),
                    "댓글 답글 수를 조회하지 못했습니다",
                )
                page_info = reply_data.get("pageInfo") or {}
                replies = int(page_info.get("totalResults")
                              if page_info.get("totalResults") is not None
                              else len(reply_data.get("items") or []))
            metrics[cid] = {
                "like_count": int(snippet.get("likeCount") or 0),
                "reply_count": replies,
            }
    return metrics


def fetch_public_comment_receipts(
    receipts: list[dict], *, api_key: str | None, session=None,
) -> dict[str, dict]:
    """Read visible comments by ID without OAuth, preserving the supplied video binding.

    Never infer that an absent result is deleted: it can be hidden, moderated,
    restricted or temporarily unavailable. The caller must never persist these
    readings as an authenticated channel ownership claim.
    """
    if len(receipts) > 50:
        raise ValueError("한 번에 댓글 50개 이하만 조회할 수 있습니다.")
    key = _require_key(api_key)
    http = session or requests.Session()
    expected: dict[str, str] = {}
    for entry in receipts:
        cid = entry["comment_id"]
        vid = entry["video_id"]
        if cid in expected and expected[cid] != vid:
            raise ValueError("동일 댓글 ID에 서로 다른 영상 ID가 전달되었습니다.")
        expected[cid] = vid
    if not expected:
        return {}

    result = {comment_id: {
        "video_id": video_id, "comment_id": comment_id, "status": "unavailable",
        "like_count": None, "reply_count": None,
    } for comment_id, video_id in expected.items()}

    def _read_items(url, ids):
        response = http.get(
            url, params={"part": "snippet", "id": ",".join(ids), "key": key},
            timeout=10,
        )
        return _json_or_error(response, "공개 댓글 반응을 조회하지 못했습니다").get("items") or []

    try:
        # YouTube Data API v3: commentThreads.list by thread id. Top-level
        # comments have the complete totalReplyCount on the thread.
        for item in _read_items(YOUTUBE_COMMENT_THREADS_URL, list(expected)):
            cid = str(item.get("id") or "")
            snippet = item.get("snippet") or {}
            top_comment = (snippet.get("topLevelComment") or {}).get("snippet") or {}
            vid = str(snippet.get("videoId") or top_comment.get("videoId") or "")
            if cid not in expected or vid != expected[cid]:
                continue
            likes = top_comment.get("likeCount")
            replies = snippet.get("totalReplyCount")
            if likes is None and replies is None:
                continue
            result[cid] = {
                "video_id": vid, "comment_id": cid, "status": "active",
                "like_count": int(likes) if likes is not None else None,
                "reply_count": int(replies) if replies is not None else None,
            }
        # A saved comment can also be a reply, which cannot be found as a
        # thread id. comments.list(id=...) handles these. It does not return
        # a reply count for comments; do not make one up.
        unresolved = [cid for cid, value in result.items() if value["status"] == "unavailable"]
        if unresolved:
            url = "https://www.googleapis.com/youtube/v3/comments"
            for item in _read_items(url, unresolved):
                cid = str(item.get("id") or "")
                snippet = item.get("snippet") or {}
                vid = str(snippet.get("videoId") or "")
                if cid not in expected or vid != expected[cid]:
                    continue
                likes = snippet.get("likeCount")
                result[cid] = {
                    "video_id": vid, "comment_id": cid, "status": "active",
                    "like_count": int(likes) if likes is not None else None,
                    "reply_count": None,  # reply counts are a thread metric
                }
    except requests.RequestException as exc:
        raise YouTubeLookupError("YouTube API 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.") from exc
    return result

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
