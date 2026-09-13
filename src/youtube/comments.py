from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from src.recommender.safety_filter import get_block_reason
from src.storage.analysis_store import pop_oauth_state, save_oauth_state
from src.youtube.context import VIDEO_ID_RE

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
YOUTUBE_OAUTH_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8000/youtube/oauth/callback"
DEFAULT_TOKEN_PATH = ROOT / "data" / "runtime" / "youtube_oauth_token.json"
STATE_TTL_SECONDS = 10 * 60

# 게시 차단 사유별 사용자 안내 문구.
BLOCK_REASON_MESSAGES = {
    "empty": "게시할 댓글이 비어 있습니다.",
    "too_short": "댓글이 너무 짧습니다 (5자 이상).",
    "too_long": "댓글이 너무 깁니다 (200자 이하).",
    "profanity": "비속어가 포함되어 게시할 수 없습니다.",
    "hate_speech": "혐오/차별 표현이 포함되어 게시할 수 없습니다.",
    "threat": "위협적인 표현이 포함되어 게시할 수 없습니다.",
    "spam": "홍보/스팸으로 분류되는 표현이 포함되어 게시할 수 없습니다.",
}


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


def _oauth_config() -> tuple[str, str, str]:
    client_id = (os.getenv("YOUTUBE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("YOUTUBE_OAUTH_REDIRECT_URI") or DEFAULT_REDIRECT_URI).strip()
    if not client_id or not client_secret:
        raise YouTubeOAuthNotConfiguredError(
            "YouTube 댓글 게시용 OAuth 설정이 필요합니다: "
            "YOUTUBE_OAUTH_CLIENT_ID, YOUTUBE_OAUTH_CLIENT_SECRET"
        )
    return client_id, client_secret, redirect_uri


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


def youtube_oauth_status() -> dict:
    client_id = bool((os.getenv("YOUTUBE_OAUTH_CLIENT_ID") or "").strip())
    client_secret = bool((os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip())
    token = _load_token()
    try:
        expires_at = float(token.get("expires_at") or 0)
    except (TypeError, ValueError):
        expires_at = 0
    access_valid = bool(token.get("access_token")) and expires_at > time.time() + 60
    return {
        "configured": client_id and client_secret,
        "authorized": bool(token.get("refresh_token")) or access_valid,
        "scope": YOUTUBE_OAUTH_SCOPE,
    }


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    return verifier, challenge


def create_youtube_authorization_url() -> str:
    client_id, _, redirect_uri = _oauth_config()
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    save_oauth_state(state, verifier, time.time() + STATE_TTL_SECONDS)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
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
    client_id, client_secret, redirect_uri = _oauth_config()
    verifier = pop_oauth_state(state)
    if verifier is None:
        raise YouTubeOAuthError("OAuth state가 만료되었거나 일치하지 않습니다.")
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
    return youtube_oauth_status()


def _refresh_access_token(*, session=None, force: bool = False) -> str:
    client_id, client_secret, _ = _oauth_config()
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
                "client_id": client_id,
                "client_secret": client_secret,
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


def publish_youtube_comment(
    *,
    video_id: str,
    channel_id: str,
    comment: str,
    session=None,
) -> dict:
    video_id = video_id.strip()
    channel_id = channel_id.strip()
    comment = comment.strip()
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise YouTubeCommentPublishError("유효한 YouTube video_id가 아닙니다.", status_code=400)
    if not channel_id:
        raise YouTubeCommentPublishError("YouTube channel_id가 필요합니다.", status_code=400)
    # 추천 파이프라인에서 이미 필터를 통과했더라도, composer에서 사용자가 자유롭게
    # 편집한 텍스트가 그대로 들어올 수 있다. 외부로 나가는 마지막 지점에서 한 번 더
    # 검사해야 안전 필터가 실제 게시물에 대한 보장이 된다.
    block_reason = get_block_reason(comment)
    if block_reason is not None:
        logger.warning("youtube.publish.blocked reason=%s video_id=%s", block_reason, video_id)
        raise YouTubeCommentPublishError(
            BLOCK_REASON_MESSAGES.get(block_reason, "게시할 수 없는 댓글입니다."),
            status_code=400,
        )

    http = session or requests.Session()
    access_token = _refresh_access_token(session=http)
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
            access_token = _refresh_access_token(session=http, force=True)
            response = send(access_token)
    except requests.RequestException as exc:
        raise YouTubeCommentPublishError("YouTube 댓글 API에 연결할 수 없습니다.") from exc

    if response.status_code < 200 or response.status_code >= 300:
        detail = (getattr(response, "text", "") or "")[:500]
        mapped = response.status_code if response.status_code in {400, 401, 403, 404} else 502
        logger.warning(
            "youtube.publish.failed video_id=%s status=%s", video_id, response.status_code
        )
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
    logger.info("youtube.publish.ok video_id=%s comment_id=%s", video_id, comment_id)
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
