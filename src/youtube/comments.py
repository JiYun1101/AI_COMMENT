from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from src.storage.analysis_store import save_oauth_handshake, pop_oauth_handshake
from src.recommender.safety_filter import get_block_reason
from src.youtube.context import VIDEO_ID_RE

ROOT = Path(__file__).resolve().parents[2]
YOUTUBE_OAUTH_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8000/youtube/oauth/callback"
DEFAULT_TOKEN_PATH = ROOT / "data" / "runtime" / "youtube_oauth_token.json"
STATE_TTL_SECONDS = 10 * 60


class YouTubeOAuthError(RuntimeError):
    pass


class YouTubeOAuthNotConfiguredError(YouTubeOAuthError):
    pass


class YouTubeOAuthNotAuthorizedError(YouTubeOAuthError):
    pass


class YouTubeCommentPublishError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _oauth_config(
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
) -> tuple[str, str, str]:
    resolved_client_id = (client_id or os.getenv("YOUTUBE_OAUTH_CLIENT_ID") or "").strip()
    resolved_client_secret = (client_secret or os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip()
    resolved_redirect_uri = (
        redirect_uri or os.getenv("YOUTUBE_OAUTH_REDIRECT_URI") or DEFAULT_REDIRECT_URI
    ).strip()
    if not resolved_client_id or not resolved_client_secret:
        raise YouTubeOAuthNotConfiguredError(
            "YouTube 댓글 게시용 OAuth 설정이 필요합니다: "
            "YOUTUBE_OAUTH_CLIENT_ID, YOUTUBE_OAUTH_CLIENT_SECRET"
        )
    return resolved_client_id, resolved_client_secret, resolved_redirect_uri


def _token_path() -> Path:
    configured = (os.getenv("YOUTUBE_OAUTH_TOKEN_PATH") or "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_TOKEN_PATH


def _load_token() -> dict:
    path = _token_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_token(payload: dict) -> None:
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def disconnect_youtube_oauth() -> None:
    path = _token_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def youtube_oauth_status(
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> dict:
    resolved_client_id = bool((client_id or os.getenv("YOUTUBE_OAUTH_CLIENT_ID") or "").strip())
    resolved_client_secret = bool((client_secret or os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip())
    token = _load_token()
    try:
        expires_at = float(token.get("expires_at") or 0)
    except (TypeError, ValueError):
        expires_at = 0
    access_valid = bool(token.get("access_token")) and expires_at > time.time() + 60
    return {
        "configured": resolved_client_id and resolved_client_secret,
        "authorized": bool(token.get("refresh_token")) or access_valid,
        "scope": YOUTUBE_OAUTH_SCOPE,
    }


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    return verifier, challenge


def create_youtube_authorization_url(
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
) -> str:
    oauth_config = _oauth_config(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    resolved_client_id, _, resolved_redirect_uri = oauth_config
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    save_oauth_handshake(state, verifier, time.time() + STATE_TTL_SECONDS, oauth_config)

    params = {
        "client_id": resolved_client_id,
        "redirect_uri": resolved_redirect_uri,
        "response_type": "code",
        "scope": YOUTUBE_OAUTH_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def complete_youtube_oauth(code: str, state: str, *, session=None) -> dict:
    pending = pop_oauth_handshake(state)
    if pending is None:
        raise YouTubeOAuthError("OAuth state가 만료되었거나 일치하지 않습니다.")

    verifier, (client_id, client_secret, redirect_uri) = pending
    http = session or requests.Session()
    try:
        response = http.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise YouTubeOAuthError("Google OAuth token endpoint에 연결할 수 없습니다.") from exc

    if response.status_code < 200 or response.status_code >= 300:
        detail = (getattr(response, "text", "") or "")[:300]
        raise YouTubeOAuthError(
            f"YouTube OAuth 인증에 실패했습니다 ({response.status_code}). {detail}".strip()
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise YouTubeOAuthError("YouTube OAuth 응답을 해석할 수 없습니다.") from exc

    existing = _load_token()
    refresh_token = payload.get("refresh_token") or existing.get("refresh_token")
    access_token = payload.get("access_token")
    if not access_token:
        raise YouTubeOAuthError("OAuth 응답에 access token이 없습니다.")

    expires_in = int(payload.get("expires_in") or 3600)
    stored = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in,
        "scope": payload.get("scope") or YOUTUBE_OAUTH_SCOPE,
        "token_type": payload.get("token_type") or "Bearer",
    }
    _save_token(stored)
    return youtube_oauth_status(client_id=client_id, client_secret=client_secret)


def _refresh_access_token(
    *,
    session=None,
    force: bool = False,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
) -> str:
    resolved_client_id, resolved_client_secret, _ = _oauth_config(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    token = _load_token()
    access_token = str(token.get("access_token") or "").strip()
    expires_at = float(token.get("expires_at") or 0)
    if access_token and not force and expires_at > time.time() + 60:
        return access_token

    refresh_token = str(token.get("refresh_token") or "").strip()
    if not refresh_token:
        raise YouTubeOAuthNotAuthorizedError(
            "YouTube 계정 연결이 필요합니다. 먼저 OAuth 로그인을 완료해주세요."
        )

    http = session or requests.Session()
    try:
        response = http.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": resolved_client_id,
                "client_secret": resolved_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise YouTubeOAuthError("YouTube OAuth token 갱신에 실패했습니다.") from exc

    if response.status_code < 200 or response.status_code >= 300:
        detail = (getattr(response, "text", "") or "")[:300]
        raise YouTubeOAuthNotAuthorizedError(
            f"YouTube OAuth token 갱신에 실패했습니다 ({response.status_code}). {detail}".strip()
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise YouTubeOAuthError("YouTube OAuth 갱신 응답을 해석할 수 없습니다.") from exc

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise YouTubeOAuthError("OAuth 갱신 응답에 access token이 없습니다.")
    token.update(
        {
            "access_token": access_token,
            "refresh_token": payload.get("refresh_token") or refresh_token,
            "expires_at": time.time() + int(payload.get("expires_in") or 3600),
            "scope": payload.get("scope") or token.get("scope") or YOUTUBE_OAUTH_SCOPE,
            "token_type": payload.get("token_type") or token.get("token_type") or "Bearer",
        }
    )
    _save_token(token)
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


def publish_youtube_comment(
    *,
    video_id: str,
    channel_id: str,
    comment: str,
    session=None,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
) -> dict:
    video_id = video_id.strip()
    channel_id = channel_id.strip()
    comment = comment.strip()
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise YouTubeCommentPublishError("유효한 YouTube video_id가 아닙니다.", status_code=400)
    if not channel_id:
        raise YouTubeCommentPublishError("YouTube channel_id가 필요합니다.", status_code=400)
    block_reason = get_block_reason(comment)
    if block_reason is not None:
        raise YouTubeCommentPublishError(
            f"안전 검사를 통과하지 못한 댓글입니다: {block_reason}", status_code=422
        )

    http = session or requests.Session()
    access_token = _refresh_access_token(
        session=http,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
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

    def send(token: str):
        return http.post(
            YOUTUBE_COMMENT_THREADS_URL,
            params={"part": "snippet"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )

    try:
        response = send(access_token)
        if response.status_code == 401:
            access_token = _refresh_access_token(
                session=http,
                force=True,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
            )
            response = send(access_token)
    except requests.RequestException as exc:
        raise YouTubeCommentPublishError("YouTube 댓글 API에 연결할 수 없습니다.") from exc

    if response.status_code < 200 or response.status_code >= 300:
        reason = _youtube_error_reason(response)
        if response.status_code == 403 and reason == "ineligibleAccount":
            raise YouTubeCommentPublishError(
                "현재 연결한 Google 계정에는 댓글을 작성할 수 있는 YouTube 채널이 없습니다. "
                "같은 계정으로 YouTube에 로그인해 채널을 만든 뒤, AI COMMENT의 내 계정에서 "
                "YouTube 연결을 해제하고 다시 연결해주세요.",
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
        "video_id": video_id,
        "comment_id": comment_id,
        "comment": comment,
        "comment_url": (
            f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"
            if comment_id
            else f"https://www.youtube.com/watch?v={video_id}"
        ),
    }

YOUTUBE_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/comments"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def _authorized_request(
    http,
    method: str,
    url: str,
    *,
    client_id: str | None,
    client_secret: str | None,
    redirect_uri: str | None,
    **kwargs,
):
    """OAuth 토큰으로 요청하고, 401이면 토큰을 한 번 갱신해 재시도한다."""

    extra_headers = kwargs.pop("headers", {})

    def send(token: str):
        headers = {"Authorization": f"Bearer {token}", **extra_headers}
        return http.request(method, url, headers=headers, timeout=15, **kwargs)

    token_options = {
        "session": http,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
    response = send(_refresh_access_token(**token_options))
    if response.status_code == 401:
        response = send(_refresh_access_token(force=True, **token_options))
    return response


def _authorized_json(http, url: str, *, params: dict, failure: str, **oauth) -> dict:
    try:
        response = _authorized_request(http, "GET", url, params=params, **oauth)
    except requests.RequestException as exc:
        raise YouTubeCommentPublishError("YouTube API에 연결할 수 없습니다.") from exc
    if response.status_code < 200 or response.status_code >= 300:
        mapped = response.status_code if response.status_code in {400, 401, 403, 404} else 502
        reason = _youtube_error_reason(response)
        explanation = {
            "incompatibleParameters": "YouTube API 요청 매개변수 조합이 올바르지 않습니다.",
            "operationNotSupported": "YouTube가 해당 댓글 ID 조회 방식을 지원하지 않습니다.",
            "invalidFilters": "YouTube API 조회 조건이 올바르지 않습니다.",
            "commentNotFound": "해당 댓글이 삭제되었거나 조회할 수 없습니다.",
            "forbidden": "연결된 YouTube 계정에 댓글 조회 권한이 없습니다.",
            "quotaExceeded": "YouTube API 할당량이 초과되었습니다.",
        }.get(reason or "", "")
        detail = f" 원인: {reason} — {explanation}" if reason else " 서버 로그에서 Google API 오류를 확인해야 합니다."
        raise YouTubeCommentPublishError(
            f"{failure} ({response.status_code}).{detail}", status_code=mapped
        )
    try:
        return response.json()
    except ValueError as exc:
        raise YouTubeCommentPublishError("YouTube API 응답을 해석할 수 없습니다.") from exc


def publish_youtube_reply(
    *,
    parent_id: str,
    text: str,
    require_video_owner: bool = True,
    prevent_duplicate: bool = False,
    session=None,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
) -> dict:
    """연결된 계정이 소유한 영상의 댓글에만 답글을 단다.

    받은 댓글함은 작성자 본인 채널의 댓글을 관리하는 도구라서, 다른 채널 영상에
    답글을 다는 데 쓰이지 않도록 서버에서 영상 소유 채널과 연결 계정을 대조한다.
    """
    parent_id = parent_id.strip()
    text = text.strip()
    if not parent_id or len(parent_id) > 100:
        raise YouTubeCommentPublishError("답글을 달 댓글 ID가 올바르지 않습니다.", status_code=400)
    if not text:
        raise YouTubeCommentPublishError("게시할 답글이 비어 있습니다.", status_code=400)
    if len(text) > 10_000:
        raise YouTubeCommentPublishError("YouTube 답글이 너무 깁니다.", status_code=400)

    http = session or requests.Session()
    oauth = {"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri}

    mine = _authorized_json(
        http,
        YOUTUBE_CHANNELS_URL,
        params={"part": "id", "mine": "true"},
        failure="연결된 YouTube 채널을 확인하지 못했습니다",
        **oauth,
    )
    my_channel_ids = {item.get("id") for item in mine.get("items") or [] if item.get("id")}
    if not my_channel_ids:
        raise YouTubeCommentPublishError(
            "연결한 Google 계정에 YouTube 채널이 없습니다. 채널을 만든 뒤 다시 연결해주세요.",
            status_code=403,
        )

    thread = _authorized_json(
        http,
        YOUTUBE_COMMENT_THREADS_URL,
        params={"part": "snippet", "id": parent_id},
        failure="답글을 달 댓글을 찾지 못했습니다",
        **oauth,
    )
    items = thread.get("items") or []
    if not items:
        raise YouTubeCommentPublishError("답글을 달 댓글을 찾지 못했습니다.", status_code=404)
    snippet = items[0].get("snippet") or {}
    video_channel_id = snippet.get("channelId")
    video_id = snippet.get("videoId")
    if require_video_owner and video_channel_id not in my_channel_ids:
        raise YouTubeCommentPublishError(
            "받은 댓글함은 연결한 계정이 소유한 영상의 댓글에만 답글을 달 수 있습니다.",
            status_code=403,
        )

    if prevent_duplicate:
        # Inspect existing replies under this parent before posting. Do not
        # silently repeat an action when an earlier attempt may have succeeded.
        page_token = None
        for _ in range(5):
            params = {"part": "snippet", "parentId": parent_id, "maxResults": 100}
            if page_token:
                params["pageToken"] = page_token
            reply_page = _authorized_json(
                http, YOUTUBE_COMMENTS_URL, params=params,
                failure="기존 답글을 확인하지 못했습니다", **oauth,
            )
            if any(
                ((item.get("snippet") or {}).get("authorChannelId") or {}).get("value") in my_channel_ids
                for item in reply_page.get("items") or []
            ):
                raise YouTubeCommentPublishError(
                    "이미 내 계정으로 답글을 단 댓글입니다.", status_code=409,
                )
            page_token = reply_page.get("nextPageToken")
            if not page_token:
                break
        if page_token:
            raise YouTubeCommentPublishError(
                "기존 답글이 너무 많아 중복 게시 여부를 확인할 수 없습니다.", status_code=409,
            )

    try:
        response = _authorized_request(
            http,
            "POST",
            YOUTUBE_COMMENTS_URL,
            params={"part": "snippet"},
            headers={"Content-Type": "application/json"},
            json={"snippet": {"parentId": parent_id, "textOriginal": text}},
            **oauth,
        )
    except requests.RequestException as exc:
        raise YouTubeCommentPublishError("YouTube 댓글 API에 연결할 수 없습니다.") from exc

    if response.status_code < 200 or response.status_code >= 300:
        detail = (getattr(response, "text", "") or "")[:500]
        mapped = response.status_code if response.status_code in {400, 401, 403, 404} else 502
        raise YouTubeCommentPublishError(
            f"YouTube 답글 게시에 실패했습니다 ({response.status_code}). {detail}".strip(),
            status_code=mapped,
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise YouTubeCommentPublishError("YouTube 답글 게시 응답을 해석할 수 없습니다.") from exc

    reply_id = body.get("id")
    return {
        "posted": True,
        "parent_id": parent_id,
        "reply_id": reply_id,
        "video_id": video_id,
        "text": text,
        "comment_url": (
            f"https://www.youtube.com/watch?v={video_id}&lc={reply_id}"
            if video_id and reply_id
            else None
        ),
    }



def fetch_owned_youtube_comment(
    *, comment_id: str, video_id: str, session=None,
    client_id: str | None = None, client_secret: str | None = None,
    redirect_uri: str | None = None,
) -> dict:
    """Verify recovery of an existing comment against the OAuth channel.

    Only records a real comment authored by the connected channel.
    Never trusts a user-supplied text, author identity, or timestamp.
    """
    if not VIDEO_ID_RE.fullmatch(video_id) or not comment_id or len(comment_id) > 100:
        raise YouTubeCommentPublishError("복구할 댓글 주소가 올바르지 않습니다.", status_code=422)
    http = session or requests.Session()
    oauth = {"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri}
    owned = _authorized_json(http, YOUTUBE_CHANNELS_URL,
                             params={"part": "id", "mine": "true"},
                             failure="연결된 채널을 확인할 수 없습니다", **oauth)
    channel_ids = {item.get("id") for item in owned.get("items") or [] if item.get("id")}
    if not channel_ids:
        raise YouTubeCommentPublishError("연결된 YouTube 채널을 확인할 수 없습니다.", status_code=403)
    payload = _authorized_json(http, YOUTUBE_COMMENTS_URL,
                               params={"part": "snippet", "id": comment_id, "textFormat": "plainText"},
                               failure="YouTube에서 댓글을 조회할 수 없습니다", **oauth)
    items = payload.get("items") or []
    if not items:
        raise YouTubeCommentPublishError("이 댓글이 존재하지 않거나 접근할 수 없습니다.", status_code=404)
    snippet = items[0].get("snippet") or {}
    author = (snippet.get("authorChannelId") or {}).get("value")
    if author not in channel_ids:
        raise YouTubeCommentPublishError("연결된 계정이 작성한 댓글이 아닙니다.", status_code=403)
    # The comments resource does not include snippet.videoId. Ownership is
    # verified by OAuth authorChannelId; the supplied video association is
    # retained as unverified metadata unless YouTube explicitly provides one.
    verified_video = str(snippet.get("videoId") or "")
    resolved_video = verified_video if VIDEO_ID_RE.fullmatch(verified_video) else video_id
    return {
        "video_id": resolved_video,
        "video_match_verified": bool(verified_video),
        "comment_id": str(items[0]["id"]),
        "comment": str(snippet.get("textOriginal") or snippet.get("textDisplay") or ""),
        "published_at": snippet.get("publishedAt"),
        "comment_url": f"https://www.youtube.com/watch?v={resolved_video}&lc={comment_id}",
    }


def _require_own_comment_for_mutation(
    comment_id: str, *, http, oauth: dict,
) -> str:
    """Verify the *actual* YouTube author before changing a public comment."""
    if not comment_id or len(comment_id) > 100 or not all(
        ch.isalnum() or ch in "._-" for ch in comment_id
    ):
        raise YouTubeCommentPublishError("댓글 ID가 올바르지 않습니다.", status_code=422)
    owner = authenticated_youtube_channel(session=http, **oauth)
    payload = _authorized_json(
        http, YOUTUBE_COMMENTS_URL,
        params={"part": "snippet", "id": comment_id, "textFormat": "plainText"},
        failure="수정·삭제할 댓글을 확인하지 못했습니다", **oauth,
    )
    items = payload.get("items") or []
    if not items or str(items[0].get("id")) != comment_id:
        raise YouTubeCommentPublishError("댓글이 삭제되었거나 조회되지 않습니다.", status_code=404)
    author_id = ((items[0].get("snippet") or {}).get("authorChannelId") or {}).get("value")
    if author_id != owner["channel_id"]:
        raise YouTubeCommentPublishError(
            "현재 연결된 YouTube 채널이 작성한 댓글만 수정·삭제할 수 있습니다.",
            status_code=403,
        )
    return owner["channel_id"]


def _mutate_owned_youtube_comment(
    comment_id: str, *, method: str, new_text: str | None = None,
    session=None, client_id: str | None = None,
    client_secret: str | None = None, redirect_uri: str | None = None,
) -> dict:
    http = session or requests.Session()
    oauth = {"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri}
    owner_id = _require_own_comment_for_mutation(comment_id, http=http, oauth=oauth)
    options = {"params": {"part": "snippet"}, "json": {
        "id": comment_id, "snippet": {"textOriginal": new_text},
    }} if method == "PUT" else {"params": {"id": comment_id}}
    try:
        response = _authorized_request(
            http, method, YOUTUBE_COMMENTS_URL, **options, **oauth,
        )
    except requests.RequestException as exc:
        raise YouTubeCommentPublishError("YouTube 댓글 변경 API에 연결할 수 없습니다.") from exc
    if not 200 <= response.status_code < 300:
        reason = _youtube_error_reason(response)
        details = {
            "commentTextTooLong": "댓글이 너무 깁니다.",
            "operationNotSupported": "YouTube가 이 댓글의 API 수정을 지원하지 않습니다. YouTube에서 직접 수정해주세요.",
            "commentNotFound": "댓글을 찾을 수 없습니다.",
            "forbidden": "이 계정으로 댓글을 변경할 권한이 없습니다.",
        }
        message = details.get(reason or "", f"YouTube 댓글 변경 실패 ({response.status_code})" +
                              (f" · {reason}" if reason else ""))
        raise YouTubeCommentPublishError(
            message, status_code=response.status_code if response.status_code in {400, 401, 403, 404} else 502,
        )
    return {"comment_id": comment_id, "owner_channel_id": owner_id,
            "comment": new_text if method == "PUT" else None}


def edit_owned_youtube_comment(
    comment_id: str, text: str, *, session=None,
    client_id: str | None = None, client_secret: str | None = None,
    redirect_uri: str | None = None,
) -> dict:
    text = text.strip()
    if not text or len(text) > 10000:
        raise YouTubeCommentPublishError("댓글은 1~10,000자여야 합니다.", status_code=422)
    reason = get_block_reason(text)
    if reason is not None:
        raise YouTubeCommentPublishError(f"안전 검사를 통과하지 못한 댓글입니다: {reason}", status_code=422)
    return _mutate_owned_youtube_comment(
        comment_id, method="PUT", new_text=text, session=session,
        client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri,
    )


def delete_owned_youtube_comment(
    comment_id: str, *, session=None, client_id: str | None = None,
    client_secret: str | None = None, redirect_uri: str | None = None,
) -> dict:
    return _mutate_owned_youtube_comment(
        comment_id, method="DELETE", session=session,
        client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri,
    )


def authenticated_youtube_channel(
    *, session=None, client_id: str | None = None,
    client_secret: str | None = None, redirect_uri: str | None = None,
) -> dict:
    """Verified stable YouTube channel identity for the currently authorized OAuth token."""
    http = session or requests.Session()
    payload = _authorized_json(
        http, YOUTUBE_CHANNELS_URL,
        params={"part": "id,snippet", "mine": "true"},
        failure="현재 연결된 YouTube 계정을 확인하지 못했습니다",
        client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri,
    )
    channels = payload.get("items") or []
    if not channels or not channels[0].get("id"):
        raise YouTubeCommentPublishError(
            "연결된 Google 계정에 확인 가능한 YouTube 채널이 없습니다.", status_code=403
        )
    item = channels[0]
    return {
        "channel_id": str(item["id"]),
        "channel_title": str((item.get("snippet") or {}).get("title") or ""),
    }



def verify_owned_comment_batch(
    entries: list[dict], *, session=None,
    client_id: str | None = None, client_secret: str | None = None,
    redirect_uri: str | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """Retrieve real comments in batches and bind to the verified OAuth channel.

    Never write pasted text directly to the database. A successful OAuth token
    alone is insufficient: each restored comment must belong to that channel.
    """
    if not entries or len(entries) > 30:
        raise YouTubeCommentPublishError("한 번에 댓글 1~30개까지 등록할 수 있습니다.", status_code=422)
    owner = authenticated_youtube_channel(
        session=session, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri,
    )
    http = session or requests.Session()
    oauth = {"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri}
    unique = {}
    for entry in entries:
        vid, cid = str(entry.get("video_id") or ""), str(entry.get("comment_id") or "")
        if not VIDEO_ID_RE.fullmatch(vid) or not cid or len(cid) > 100:
            raise YouTubeCommentPublishError("댓글 주소에 올바른 영상·댓글 ID가 필요합니다.", status_code=422)
        unique[cid] = vid
    payload = _authorized_json(
        http, YOUTUBE_COMMENTS_URL,
        params={"part": "snippet", "id": ",".join(unique), "textFormat": "plainText"},
        failure="YouTube 게시 댓글을 조회할 수 없습니다", **oauth,
    )
    verified = []
    rejected = []
    records = {str(item.get("id")): item for item in (payload.get("items") or [])}
    for cid, vid in unique.items():
        item = records.get(cid)
        snippet = (item or {}).get("snippet") or {}
        if not item:
            rejected.append({"comment_id": cid, "reason": "YouTube에서 찾을 수 없는 댓글"})
        elif (snippet.get("authorChannelId") or {}).get("value") != owner["channel_id"]:
            rejected.append({"comment_id": cid, "reason": "현재 연결한 채널의 댓글이 아님"})
        else:
            # Author ownership is authoritative. comments.list does NOT return
            # snippet.videoId, so Takeout's videoId must not be treated as a
            # failed YouTube verification. Store provenance for transparency.
            actual_video = str(snippet.get("videoId") or "")
            video_verified = bool(VIDEO_ID_RE.fullmatch(actual_video))
            resolved_video = actual_video if video_verified else vid
            verified.append({
                "video_id": resolved_video,
                "video_match_verified": video_verified,
                "comment_id": cid,
                "comment": str(snippet.get("textOriginal") or snippet.get("textDisplay") or ""),
                "published_at": snippet.get("publishedAt"),
                "comment_url": f"https://www.youtube.com/watch?v={resolved_video}&lc={cid}",
            })
    return verified, rejected, owner
