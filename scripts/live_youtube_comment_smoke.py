from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from yt_dlp import YoutubeDL

from src.youtube.comments import publish_youtube_comment
from src.youtube.context import extract_video_id

VIDEO_URL = os.getenv(
    "YOUTUBE_LIVE_TEST_VIDEO_URL",
    "https://www.youtube.com/watch?v=hCZAcNPrq1I",
)
TEST_COMMENT = os.getenv(
    "YOUTUBE_LIVE_TEST_COMMENT",
    "[AI Comment Recommender live test] 자동 댓글 게시 기능 확인 후 삭제되는 테스트 댓글입니다.",
)
TOKEN_PATH = Path("/tmp/youtube_oauth_token.json")


def _secret_ready(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def _prepare_token_file() -> None:
    token_json = (os.getenv("YOUTUBE_OAUTH_TOKEN_JSON") or "").strip()
    refresh_token = (os.getenv("YOUTUBE_OAUTH_REFRESH_TOKEN") or "").strip()
    access_token = (os.getenv("YOUTUBE_OAUTH_ACCESS_TOKEN") or "").strip()

    if token_json:
        try:
            payload = json.loads(token_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("YOUTUBE_OAUTH_TOKEN_JSON is not valid JSON") from exc
    elif refresh_token:
        payload = {"refresh_token": refresh_token, "expires_at": 0}
    elif access_token:
        payload = {"access_token": access_token, "expires_at": 4102444800}
    else:
        raise RuntimeError(
            "Missing OAuth token secret: set YOUTUBE_OAUTH_REFRESH_TOKEN, "
            "YOUTUBE_OAUTH_TOKEN_JSON, or YOUTUBE_OAUTH_ACCESS_TOKEN"
        )

    TOKEN_PATH.write_text(json.dumps(payload), encoding="utf-8")
    os.environ["YOUTUBE_OAUTH_TOKEN_PATH"] = str(TOKEN_PATH)


def _channel_id(video_url: str) -> str:
    with YoutubeDL(
        {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
    ) as ydl:
        info = ydl.extract_info(video_url, download=False)
    channel_id = str(info.get("channel_id") or "").strip()
    if not channel_id.startswith("UC"):
        raise RuntimeError(f"Could not resolve uploader channel_id for video: {video_url}")
    return channel_id


def _authorization_header() -> dict[str, str]:
    payload = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("Publisher did not persist a usable access token")
    return {"Authorization": f"Bearer {access_token}"}


def main() -> int:
    required = ["YOUTUBE_OAUTH_CLIENT_ID", "YOUTUBE_OAUTH_CLIENT_SECRET"]
    missing = [name for name in required if not _secret_ready(name)]
    has_token = any(
        _secret_ready(name)
        for name in (
            "YOUTUBE_OAUTH_REFRESH_TOKEN",
            "YOUTUBE_OAUTH_TOKEN_JSON",
            "YOUTUBE_OAUTH_ACCESS_TOKEN",
        )
    )
    print(
        "LIVE_SMOKE_AUTH="
        + json.dumps(
            {
                "client_id": _secret_ready("YOUTUBE_OAUTH_CLIENT_ID"),
                "client_secret": _secret_ready("YOUTUBE_OAUTH_CLIENT_SECRET"),
                "token": has_token,
            }
        )
    )
    if missing or not has_token:
        print(
            "LIVE_SMOKE_BLOCKED="
            + json.dumps(
                {
                    "reason": "missing_oauth_credentials",
                    "missing": missing + ([] if has_token else ["oauth_token_secret"]),
                }
            )
        )
        return 2

    _prepare_token_file()
    video_id = extract_video_id(VIDEO_URL)
    channel_id = _channel_id(VIDEO_URL)
    print(
        "LIVE_SMOKE_TARGET="
        + json.dumps({"video_id": video_id, "channel_id": channel_id})
    )

    comment_id: str | None = None
    inserted = False
    verified = False
    deleted = False
    cleanup_status: int | None = None

    try:
        posted = publish_youtube_comment(
            video_id=video_id,
            channel_id=channel_id,
            comment=TEST_COMMENT,
        )
        inserted = bool(posted.get("posted"))
        comment_id = str(posted.get("comment_id") or "").strip() or None
        if not inserted or not comment_id:
            raise RuntimeError(f"Insert response did not contain a comment id: {posted}")

        headers = _authorization_header()
        verify_response = requests.get(
            "https://www.googleapis.com/youtube/v3/comments",
            params={"part": "snippet", "id": comment_id},
            headers=headers,
            timeout=15,
        )
        if verify_response.status_code != 200:
            raise RuntimeError(
                f"Inserted comment could not be read back ({verify_response.status_code}): "
                f"{verify_response.text[:300]}"
            )
        verify_body = verify_response.json()
        items = verify_body.get("items") or []
        if not items:
            raise RuntimeError("Inserted comment id was not returned by comments.list")

        snippet = items[0].get("snippet") or {}
        actual_text = str(snippet.get("textOriginal") or "")
        if actual_text != TEST_COMMENT:
            raise RuntimeError("Read-back comment text did not match inserted text")
        verified = True

        delete_response = requests.delete(
            "https://www.googleapis.com/youtube/v3/comments",
            params={"id": comment_id},
            headers=headers,
            timeout=15,
        )
        cleanup_status = delete_response.status_code
        deleted = delete_response.status_code == 204
        if not deleted:
            raise RuntimeError(
                f"Cleanup delete failed ({delete_response.status_code}): "
                f"{delete_response.text[:300]}"
            )

        print(
            "LIVE_SMOKE_RESULT="
            + json.dumps(
                {
                    "inserted": inserted,
                    "verified_by_id": verified,
                    "deleted_after_verification": deleted,
                    "video_id": video_id,
                    "comment_id": comment_id,
                    "cleanup_status": cleanup_status,
                }
            )
        )
        return 0
    finally:
        if comment_id and inserted and not deleted:
            try:
                headers = _authorization_header()
                response = requests.delete(
                    "https://www.googleapis.com/youtube/v3/comments",
                    params={"id": comment_id},
                    headers=headers,
                    timeout=15,
                )
                print(
                    "LIVE_SMOKE_EMERGENCY_CLEANUP="
                    + json.dumps(
                        {
                            "comment_id": comment_id,
                            "status": response.status_code,
                            "deleted": response.status_code == 204,
                        }
                    )
                )
            except Exception as exc:
                print(f"LIVE_SMOKE_EMERGENCY_CLEANUP_ERROR={type(exc).__name__}")


if __name__ == "__main__":
    sys.exit(main())
