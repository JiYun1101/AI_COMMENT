from __future__ import annotations

import html
import secrets
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from src.api.security import auth_status, create_paired_session, require_trusted_client
from src.audience.reactions import build_observation_report
from src.storage.audience_store import (
    save_audience_observation, list_audience_observations, read_audience_observation,
)
from casts.comment_writer.graph import comment_writer_graph
from src.logging_config import configure_logging
from src.api.schemas import (
    CreatorReplyRequest,
    FeedbackRequest,
    RecommendRequest,
    ReplyDraftRequest,
    ScoreRequest,
    YouTubeCommentPublishRequest,
)
from src.creator.inbox import build_inbox
from src.creator.reply_drafts import draft_replies
from src.llm.openai_client import LLMGenerationError, LLMNotReadyError, OpenAIResponsesClient
from src.llm.provider import llm_readiness
from src.model.predict import ModelNotReadyError, model_readiness, score_comments
from src.recommender.generation_context import build_generation_context, summarize_generation_context
from src.recommender.persona import resolve_persona, build_custom_persona
from src.recommender.ranker import recommend_comments_with_meta
from src.recommender.safety_filter import get_block_reason
from src.storage.published_store import (
    apply_comment_metrics,
    comment_ids_to_refresh,
    list_published_comments,
    published_summary,
    record_published_comment,
    update_owned_published_text,
    delete_owned_published_record,
    list_legacy_unbound_comments,
    attach_verified_legacy_comment,
)
from src.storage.model_progress import model_data_progress
from src.storage.analysis_store import (
    dashboard_summary,
    get_analysis,
    init_db,
    list_analyses,
    list_comments,
    save_analysis,
    set_feedback,
)
from src.youtube.comments import (
    YouTubeCommentPublishError,
    YouTubeOAuthError,
    YouTubeOAuthNotAuthorizedError,
    YouTubeOAuthNotConfiguredError,
    complete_youtube_oauth,
    create_youtube_authorization_url,
    disconnect_youtube_oauth,
    publish_youtube_comment,
    publish_youtube_reply,
    edit_owned_youtube_comment,
    delete_owned_youtube_comment,
    fetch_owned_youtube_comment,
    verify_owned_comment_batch,
    authenticated_youtube_channel,
    youtube_oauth_status,
)
from src.youtube.engagement import fetch_comment_metrics, fetch_video_comment_threads, fetch_public_comment_receipts
from src.youtube.video_performance import fetch_my_videos, fetch_owned_video
from src.storage.video_store import (
    list_video_metrics, recently_synced, save_video_metrics,
)
from src.youtube.demo import (
    DemoYouTubeNotConfiguredError,
    DemoYouTubeRateLimitError,
    demo_status,
    demo_visitor_key,
    publish_demo_youtube_comment,
)
from src.youtube.context import (
    VIDEO_ID_RE,
    InvalidYouTubeUrlError,
    YouTubeConfigurationError,
    YouTubeLookupError,
    build_reference_text,
    fetch_youtube_context,
    extract_video_id,
)

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Comment Recommender",
    description="Deterministic context engineering + LLM generation + reaction ranking",
    version="0.5.0",
)

_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra_origins = [
    value.strip()
    for value in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if value.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_default_origins, *_extra_origins],
    allow_origin_regex=os.getenv("CORS_ALLOWED_ORIGIN_REGEX") or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


class PairingRequest(BaseModel):
    pairing_code: str = Field(min_length=32, max_length=256)


@app.post("/auth/connect")
def connect_browser_to_server(payload: PairingRequest):
    """Exchange a private owner invitation for a time-limited browser credential."""
    result = create_paired_session(payload.pairing_code)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@app.get("/auth/session", dependencies=[Depends(require_trusted_client)])
def check_server_session():
    return {"connected": True}


@app.get("/health")
def health_check():
    model = model_readiness()
    llm = llm_readiness()
    demo = demo_status()
    if not llm.get("ready") and demo.get("openai_configured"):
        llm = {
            "ready": True,
            "provider": "openai_responses_api",
            "selection": "demo",
            "model": (os.getenv("DEMO_OPENAI_MODEL") or "").strip(),
            "missing": [],
        }
    return {
        "status": "ok" if model["ready"] and llm["ready"] else "degraded",
        "message": "AI Comment Recommender API is running",
        "model": model,
        "llm": llm,
        "youtube": {
            "configured": bool(
                (os.getenv("YOUTUBE_API_KEY") or "").strip()
                or (os.getenv("DEMO_YOUTUBE_API_KEY") or "").strip()
            ),
            "oauth": youtube_oauth_status(),
            "demo": demo,
        },
        "storage": {
            "ready": True,
            "persistent": os.getenv("AI_COMMENT_STORAGE_PERSISTENT", "").lower() == "true",
            "warning": (
                None if os.getenv("AI_COMMENT_STORAGE_PERSISTENT", "").lower() == "true"
                else "SQLite 저장소의 영구 보존이 확인되지 않았습니다. 재배포 시 기록이 유실될 수 있습니다."
            ),
        },
        "auth": auth_status(),
    }


def _normalize_header(value: str | None, *, label: str, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise HTTPException(status_code=400, detail=f"{label} 형식이 올바르지 않습니다.")
    return normalized


def _normalize_youtube_api_key(value: str | None) -> str | None:
    return _normalize_header(value, label="YouTube API Key", max_length=256)


def _normalize_openai_api_key(value: str | None) -> str | None:
    return _normalize_header(value, label="OpenAI API Key", max_length=512)


def _normalize_openai_model(value: str | None) -> str | None:
    return _normalize_header(value, label="OpenAI 모델명", max_length=120)


def _normalize_oauth_client_id(value: str | None) -> str | None:
    return _normalize_header(value, label="YouTube OAuth Client ID", max_length=512)


def _normalize_oauth_client_secret(value: str | None) -> str | None:
    return _normalize_header(value, label="YouTube OAuth Client Secret", max_length=512)


def _normalize_oauth_redirect_uri(value: str | None) -> str | None:
    return _normalize_header(value, label="YouTube OAuth Redirect URI", max_length=2048)


def _normalize_account_mode(value: str | None) -> str:
    mode = (value or "demo").strip().lower()
    if mode not in {"demo", "personal"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 계정 모드입니다.")
    return mode


def _youtube_context_or_http_error(url: str, api_key: str | None = None):
    try:
        return fetch_youtube_context(url, api_key=_normalize_youtube_api_key(api_key))
    except InvalidYouTubeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except YouTubeConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _generation_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (LLMNotReadyError, ModelNotReadyError)):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, LLMGenerationError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail="추천 생성 중 오류가 발생했습니다.")


@app.get("/videos/preview")
def preview_youtube_video(
    url: str = Query(..., min_length=1),
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
):
    mode = _normalize_account_mode(account_mode)
    resolved_key = _normalize_youtube_api_key(youtube_api_key)
    if mode == "demo" and not resolved_key:
        resolved_key = _normalize_youtube_api_key(os.getenv("DEMO_YOUTUBE_API_KEY"))
    return _youtube_context_or_http_error(url, resolved_key).to_dict()


@app.get("/videos/moments", dependencies=[Depends(require_trusted_client)])
def video_caption_moments(url: str = Query(..., min_length=1, max_length=500)):
    """Time-aligned caption evidence; NOT a claim of visual understanding."""
    from src.youtube.video_moments import get_video_caption_moments
    try:
        video_id = extract_video_id(url)
    except InvalidYouTubeUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return get_video_caption_moments(video_id)


@app.get("/youtube/oauth/status", dependencies=[Depends(require_trusted_client)])
def youtube_oauth_connection_status(
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    return youtube_oauth_status(
        client_id=_normalize_oauth_client_id(oauth_client_id),
        client_secret=_normalize_oauth_client_secret(oauth_client_secret),
    )


@app.get("/youtube/oauth/start", dependencies=[Depends(require_trusted_client)])
def youtube_oauth_start(
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    try:
        return {
            "authorization_url": create_youtube_authorization_url(
                client_id=_normalize_oauth_client_id(oauth_client_id),
                client_secret=_normalize_oauth_client_secret(oauth_client_secret),
                redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
            )
        }
    except YouTubeOAuthNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/youtube/oauth/callback", response_class=HTMLResponse)
def youtube_oauth_callback(code: str = Query(...), state: str = Query(...)):
    try:
        complete_youtube_oauth(code, state)
    except YouTubeOAuthError as exc:
        return HTMLResponse(
            content=(
                "<!doctype html><meta charset='utf-8'><title>YouTube 연결 실패</title>"
                "<body style='font-family:sans-serif;padding:32px'>"
                f"<h2>YouTube 연결 실패</h2><p>{html.escape(str(exc))}</p>"
                "</body>"
            ),
            status_code=400,
        )
    return HTMLResponse(
        content=(
            "<!doctype html><meta charset='utf-8'><title>YouTube 연결 완료</title>"
            "<body style='font-family:sans-serif;padding:32px'>"
            "<h2>YouTube 계정 연결 완료</h2>"
            "<p>이 창은 자동으로 닫힙니다.</p>"
            "<script>setTimeout(() => window.close(), 700)</script>"
            "</body>"
        )
    )


@app.post("/youtube/oauth/disconnect", dependencies=[Depends(require_trusted_client)])
def youtube_oauth_disconnect(
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    disconnect_youtube_oauth()
    return youtube_oauth_status(
        client_id=_normalize_oauth_client_id(oauth_client_id),
        client_secret=_normalize_oauth_client_secret(oauth_client_secret),
    )


def _request_identity(request: Request) -> str:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    return request.client.host if request.client else "anonymous"


@app.get("/youtube/demo/status")
def youtube_demo_status(request: Request):
    visitor_key = demo_visitor_key(_request_identity(request))
    return demo_status(visitor_key)


@app.post("/youtube/comments")
def youtube_comment_publish(
    request: Request,
    payload: YouTubeCommentPublishRequest,
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    normalized_mode = _normalize_account_mode(account_mode)
    if normalized_mode == "personal":
        require_trusted_client(request)

    if normalized_mode == "demo":
        visitor_key = demo_visitor_key(_request_identity(request))
        try:
            result = publish_demo_youtube_comment(
                video_id=payload.video_id,
                channel_id=payload.channel_id,
                comment=payload.comment,
                visitor_key=visitor_key,
            )
        except DemoYouTubeNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except DemoYouTubeRateLimitError as exc:
            raise HTTPException(
                status_code=429,
                detail=f"{exc} 잠시 후 다시 시도해주세요.",
                headers={"Retry-After": str(exc.retry_after_seconds)},
            ) from exc
        except YouTubeCommentPublishError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        return _track_published_comment(result, payload, normalized_mode)

    try:
        result = publish_youtube_comment(
            video_id=payload.video_id,
            channel_id=payload.channel_id,
            comment=payload.comment,
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
    except YouTubeOAuthNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeOAuthNotAuthorizedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except YouTubeOAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _track_published_comment(result, payload, normalized_mode)


def _track_published_comment(result: dict, payload: YouTubeCommentPublishRequest, mode: str) -> dict:
    """Publish result must disclose failed persistence; browser can retain a backup."""
    comment_id = result.get("comment_id")
    if not comment_id:
        return {**result, "tracked": False, "tracking_warning": "YouTube 게시 ID가 없어 추적할 수 없습니다."}
    try:
        record_published_comment(
            video_id=result.get("video_id") or payload.video_id,
            comment_id=str(comment_id),
            comment=result.get("comment") or payload.comment,
            comment_url=result.get("comment_url"),
            account_mode=mode,
            owner_channel_id=(
                authenticated_youtube_channel()["channel_id"] if mode == "personal" else None
            ),
            recommendation_id=payload.recommendation_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("published comment tracking failed")
        return {**result, "tracked": False, "tracking_warning": "YouTube 게시는 완료됐지만 서버 추적 기록을 저장하지 못했습니다."}
    return {**result, "tracked": True}


def _resolve_youtube_api_key(header_value: str | None, mode: str) -> str:
    resolved = _normalize_youtube_api_key(header_value)
    if not resolved:
        env_names = ("DEMO_YOUTUBE_API_KEY", "YOUTUBE_API_KEY") if mode == "demo" else ("YOUTUBE_API_KEY",)
        resolved = next(
            (os.getenv(name, "").strip() for name in env_names if os.getenv(name, "").strip()),
            None,
        )
    if not resolved:
        raise HTTPException(status_code=503, detail="YouTube API key가 필요합니다. 계정 설정에서 연결해주세요.")
    return resolved


class RecoverCommentRequest(BaseModel):
    video_id: str = Field(min_length=11, max_length=11)
    comment_id: str = Field(min_length=1, max_length=100)


@app.post("/my-comments/recover", dependencies=[Depends(require_trusted_client)])
def recover_published_comment(
    payload: RecoverCommentRequest,
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    """Re-attach public YouTube comments, but ONLY if OAuth proves authorship."""
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 계정으로 연결해야 댓글을 복구할 수 있습니다.")
    try:
        original = fetch_owned_youtube_comment(
            comment_id=payload.comment_id, video_id=payload.video_id,
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
        identity = _verified_account_channel(
            "personal", oauth_client_id, oauth_client_secret, oauth_redirect_uri
        )
        stored_id = record_published_comment(
            video_id=original["video_id"], comment_id=original["comment_id"],
            comment=original["comment"], comment_url=original["comment_url"],
            account_mode="personal", owner_channel_id=identity["channel_id"],
            published_at=original["published_at"],
        )
    except (YouTubeOAuthNotConfiguredError, YouTubeOAuthNotAuthorizedError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"tracked": True, "id": stored_id, **original}




class RecoverCommentBatchRequest(BaseModel):
    comments: list[RecoverCommentRequest] = Field(min_length=1, max_length=30)


@app.post("/my-comments/recover/batch", dependencies=[Depends(require_trusted_client)])
def recover_published_batch(
    payload: RecoverCommentBatchRequest,
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 YouTube 계정을 연결해야 복구할 수 있습니다.")
    try:
        verified, rejected, owner = verify_owned_comment_batch(
            [row.model_dump() for row in payload.comments],
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
    except (YouTubeOAuthNotConfiguredError, YouTubeOAuthNotAuthorizedError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    saved = []
    for row in verified:
        try:
            record_id = record_published_comment(
                video_id=row["video_id"], comment_id=row["comment_id"], comment=row["comment"],
                comment_url=row["comment_url"], published_at=row["published_at"],
                account_mode="personal", owner_channel_id=owner["channel_id"],
            )
            saved.append({"id": record_id, **row})
        except Exception:
            logger.exception("batch comment recovery persistence failed")
            rejected.append({"comment_id": row["comment_id"], "reason": "서버 기록 저장에 실패했습니다"})
    return {
        "owner_channel_id": owner["channel_id"],
        "registered_count": len(saved), "failed_count": len(rejected),
        "items": saved, "failures": rejected,
        "storage_persistent": os.getenv("AI_COMMENT_STORAGE_PERSISTENT", "").lower() == "true",
    }



def _verified_account_channel(
    account_mode: str,
    oauth_client_id: str | None = None,
    oauth_client_secret: str | None = None,
    oauth_redirect_uri: str | None = None,
) -> dict | None:
    if _normalize_account_mode(account_mode) != "personal":
        return None
    try:
        return authenticated_youtube_channel(
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
    except (YouTubeOAuthNotAuthorizedError, YouTubeOAuthNotConfiguredError) as exc:
        raise HTTPException(status_code=401, detail="같은 YouTube 계정을 다시 연결해주세요. " + str(exc)) from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


# Video performance is always tied to the authenticated YouTube channel.
# Unlike public /videos/preview, none of these endpoints accepts a channel ID
# supplied by the browser or accesses another creator's private inventory.
def _my_videos_identity(account_mode, oauth_client_id, oauth_client_secret):
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="내 영상 성과는 개인 YouTube 계정 연결 후 이용할 수 있습니다.")
    return _verified_account_channel("personal", oauth_client_id, oauth_client_secret)


def _my_videos_payload(channel_id):
    result = list_video_metrics(channel_id)
    persistent = os.getenv("AI_COMMENT_STORAGE_PERSISTENT", "").lower() in {"1", "true", "yes"}
    result["storage_persistent"] = persistent
    result["storage_warning"] = None if persistent else (
        "서버가 영구 저장소를 사용하지 않아 재시작 시 추적 기록이 사라질 수 있습니다. "
        "JSON 백업도 보관해주세요."
    )
    return result


class TrackOwnedVideoRequest(BaseModel):
    video_id: str = Field(min_length=11, max_length=11, pattern=r"^[A-Za-z0-9_-]{11}$")


@app.get("/my-videos", dependencies=[Depends(require_trusted_client)])
def my_video_performance(
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    identity = _my_videos_identity(account_mode, oauth_client_id, oauth_client_secret)
    return _my_videos_payload(identity["channel_id"])


@app.post("/my-videos/refresh", dependencies=[Depends(require_trusted_client)])
def refresh_my_video_performance(
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    identity = _my_videos_identity(account_mode, oauth_client_id, oauth_client_secret)
    channel_id = identity["channel_id"]
    if recently_synced(channel_id):
        return {**_my_videos_payload(channel_id), "checked_count": 0, "cached": True}
    try:
        report = fetch_my_videos(
            limit=None,
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
        )
    except (YouTubeOAuthNotAuthorizedError, YouTubeOAuthNotConfiguredError) as exc:
        raise HTTPException(status_code=401, detail="YouTube 계정을 다시 연결해주세요.") from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except YouTubeOAuthError as exc:
        raise HTTPException(status_code=502, detail="YouTube 인증 서버에 연결할 수 없습니다.") from exc
    if report["channel_id"] != channel_id:
        raise HTTPException(status_code=403, detail="현재 연결된 채널의 영상만 추적할 수 있습니다.")
    count = save_video_metrics(channel_id, report["channel_title"], report["videos"])
    return {**_my_videos_payload(channel_id), "checked_count": count,
            "cached": False, "limit_reached": report["limit_reached"]}


@app.post("/my-videos/track", dependencies=[Depends(require_trusted_client)])
def track_owned_video(
    payload: TrackOwnedVideoRequest,
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    identity = _my_videos_identity(account_mode, oauth_client_id, oauth_client_secret)
    try:
        report = fetch_owned_video(
            payload.video_id,
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
        )
    except (YouTubeOAuthNotAuthorizedError, YouTubeOAuthNotConfiguredError) as exc:
        raise HTTPException(status_code=401, detail="YouTube 계정을 다시 연결해주세요.") from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except YouTubeOAuthError as exc:
        raise HTTPException(status_code=502, detail="YouTube 인증 서버에 연결할 수 없습니다.") from exc
    if report["channel_id"] != identity["channel_id"]:
        raise HTTPException(status_code=403, detail="다른 채널의 영상은 추적할 수 없습니다.")
    save_video_metrics(identity["channel_id"], report["channel_title"],
                       report["videos"], mark_sync=False)
    return {**_my_videos_payload(identity["channel_id"]), "added_video_id": payload.video_id}


@app.get("/account/youtube-identity", dependencies=[Depends(require_trusted_client)])
def verified_account_identity(
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    result = _verified_account_channel(
        "personal", oauth_client_id, oauth_client_secret, oauth_redirect_uri,
    )
    return {"connected": True, **result}

@app.post("/my-comments/claim-legacy", dependencies=[Depends(require_trusted_client)])
def claim_legacy_published_history(
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    """Attach old unscoped SQLite records only after checking exact YouTube authorship."""
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 YouTube 계정 연결이 필요합니다.")
    identity = _verified_account_channel(
        account_mode, oauth_client_id, oauth_client_secret, oauth_redirect_uri,
    )
    seen, restored = 0, 0
    for item in list_legacy_unbound_comments(limit=20):
        seen += 1
        try:
            fetch_owned_youtube_comment(
                comment_id=item["comment_id"], video_id=item["video_id"],
                client_id=_normalize_oauth_client_id(oauth_client_id),
                client_secret=_normalize_oauth_client_secret(oauth_client_secret),
                redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
            )
        except (YouTubeCommentPublishError, YouTubeOAuthError):
            continue
        if attach_verified_legacy_comment(item["comment_id"], identity["channel_id"]):
            restored += 1
    return {"checked": seen, "restored": restored, "remaining": len(list_legacy_unbound_comments(limit=100))}


class EditPublishedCommentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


@app.put("/my-comments/{comment_id}", dependencies=[Depends(require_trusted_client)])
def edit_my_published_comment(
    comment_id: str,
    payload: EditPublishedCommentRequest,
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 계정의 본인 댓글만 수정할 수 있습니다.")
    try:
        changed = edit_owned_youtube_comment(
            comment_id, payload.text,
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
    except (YouTubeOAuthNotConfiguredError, YouTubeOAuthNotAuthorizedError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    saved = False
    try:
        saved = update_owned_published_text(
            comment_id, changed["owner_channel_id"], changed["comment"],
        )
    except Exception:
        logger.exception("YouTube edit succeeded but tracking text sync failed")
    return {"updated": True, "comment_id": comment_id,
            "comment": changed["comment"], "tracking_saved": saved}


@app.delete("/my-comments/{comment_id}", dependencies=[Depends(require_trusted_client)])
def delete_my_published_comment(
    comment_id: str,
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 계정의 본인 댓글만 삭제할 수 있습니다.")
    try:
        deleted = delete_owned_youtube_comment(
            comment_id, client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
    except (YouTubeOAuthNotConfiguredError, YouTubeOAuthNotAuthorizedError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    removed = False
    try:
        removed = delete_owned_published_record(comment_id, deleted["owner_channel_id"])
    except Exception:
        logger.exception("YouTube deletion succeeded but tracking record removal failed")
    return {"deleted": True, "comment_id": comment_id, "tracking_removed": removed}


@app.get("/my-comments/export", dependencies=[Depends(require_trusted_client)])
def export_my_comments(
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    """Account-scoped, read-only recovery snapshot. Never export other accounts."""
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 계정에서만 댓글 기록을 백업할 수 있습니다.")
    identity = _verified_account_channel("personal", oauth_client_id, oauth_client_secret)
    rows = list_published_comments(
        account_mode="personal", owner_channel_id=identity["channel_id"], limit=501,
    )
    if len(rows) > 500:
        raise HTTPException(
            status_code=409, detail="댓글이 500개를 초과합니다. 일부 데이터만 백업하지 않도록 내보내기를 중단했습니다.",
        )
    return JSONResponse(
        {"format": "ai-comment-published-backup-v1",
         "exported_at": datetime.now(timezone.utc).isoformat(),
         "channel_id": identity["channel_id"], "comments": rows},
        headers={"Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="ai-comment-owned-comments.json"'},
    )


@app.get("/my-comments", dependencies=[Depends(require_trusted_client)])
def my_published_comments(
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    limit: int = Query(default=100, ge=1, le=300),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    mode = _normalize_account_mode(account_mode)
    identity = _verified_account_channel(mode, oauth_client_id, oauth_client_secret)
    items = list_published_comments(account_mode=mode, owner_channel_id=identity["channel_id"] if identity else None, limit=limit)
    return {"summary": published_summary(items), "items": items}


class PublicCommentReceipt(BaseModel):
    video_id: str = Field(min_length=11, max_length=11, pattern=r"^[A-Za-z0-9_-]{11}$")
    comment_id: str = Field(min_length=5, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")


class PublicCommentMetricsRequest(BaseModel):
    comments: list[PublicCommentReceipt] = Field(min_length=1, max_length=50)


@app.post("/my-comments/public-metrics", dependencies=[Depends(require_trusted_client)])
def public_published_comment_metrics(
    payload: PublicCommentMetricsRequest,
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
):
    """Read-only public YouTube counters, even when server DB/OAuth has reset.

    Reading a publicly visible comment does NOT establish its ownership.
    Never write these unverified readings to the account-scoped server DB.
    """
    mode = _normalize_account_mode(account_mode)
    api_key = _resolve_youtube_api_key(youtube_api_key, mode)
    try:
        observed = fetch_public_comment_receipts(
            [entry.model_dump() for entry in payload.comments], api_key=api_key,
        )
    except YouTubeConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeLookupError as exc:
        raise HTTPException(
            status_code=502,
            detail="YouTube 댓글 정보를 조회하지 못했습니다. API 키·할당량·댓글 공개 상태를 확인해주세요.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rows = list(observed.values())
    return {
        "checked_count": len(rows),
        "observed_count": sum(row["status"] == "active" for row in rows),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "items": rows,
        "storage": "browser_only",
    }


@app.post("/my-comments/refresh", dependencies=[Depends(require_trusted_client)])
def refresh_my_published_comments(
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    mode = _normalize_account_mode(account_mode)
    identity = _verified_account_channel(mode, oauth_client_id, oauth_client_secret)
    owner_id = identity["channel_id"] if identity else None
    comment_ids = comment_ids_to_refresh(account_mode=mode, owner_channel_id=owner_id)
    updated = 0
    if comment_ids:
        api_key = _resolve_youtube_api_key(youtube_api_key, mode)
        try:
            metrics = fetch_comment_metrics(comment_ids, api_key=api_key)
        except YouTubeConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except YouTubeLookupError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        updated = apply_comment_metrics(comment_ids, metrics)
    items = list_published_comments(account_mode=mode, owner_channel_id=owner_id)
    return {"checked_count": updated, "summary": published_summary(items), "items": items}


def _observed_report(
    video_id: str, analysis_id: str | None,
    youtube_api_key: str | None, account_mode: str,
) -> dict:
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise HTTPException(status_code=422, detail="유효한 YouTube 영상 ID가 아닙니다.")

    analysis = None
    if analysis_id:
        analysis = get_analysis(analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="예상 반응 분석을 찾을 수 없습니다.")
        if analysis.get("video_id") != video_id:
            raise HTTPException(status_code=422, detail="예상 반응 분석과 실제 영상이 일치하지 않습니다.")

    key = _resolve_youtube_api_key(youtube_api_key, _normalize_account_mode(account_mode))
    try:
        # One bounded live sample, not full channel history or a random audience.
        threads = fetch_video_comment_threads(
            video_id, api_key=key, order="relevance", limit=100,
        )
    except YouTubeConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    report = build_observation_report(
        video_id, threads,
        recommendations=analysis["recommendations"] if analysis is not None else None,
    )
    report["analysis_id"] = analysis_id
    return report


@app.get("/audience/observed")
def audience_observed(
    video_id: str = Query(..., min_length=11, max_length=11),
    analysis_id: str | None = Query(default=None, max_length=40),
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
):
    """Read-only observed reaction analysis works even when LLM isn't configured."""
    return _observed_report(video_id, analysis_id, youtube_api_key, account_mode)


@app.post("/audience/observations", dependencies=[Depends(require_trusted_client)])
def store_audience_observation(
    video_id: str = Query(..., min_length=11, max_length=11),
    analysis_id: str | None = Query(default=None, max_length=40),
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
):
    """Fetch directly from YouTube before persisting; clients cannot forge memory."""
    report = _observed_report(video_id, analysis_id, youtube_api_key, account_mode)
    snapshot = save_audience_observation(report, analysis_id=analysis_id)
    return {"snapshot": snapshot, "report": report}


@app.get("/audience/observations/{video_id}", dependencies=[Depends(require_trusted_client)])
def audience_observation_history(video_id: str):
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise HTTPException(status_code=422, detail="유효한 YouTube 영상 ID가 아닙니다.")
    return {"items": list_audience_observations(video_id)}


@app.get("/audience/observations/snapshot/{snapshot_id}", dependencies=[Depends(require_trusted_client)])
def audience_observation_snapshot(snapshot_id: str):
    if not snapshot_id.startswith("obs_") or len(snapshot_id) > 36:
        raise HTTPException(status_code=422, detail="유효한 스냅샷 ID가 아닙니다.")
    result = read_audience_observation(snapshot_id)
    if result is None:
        raise HTTPException(status_code=404, detail="저장된 스냅샷이 없습니다.")
    return result


@app.get("/creator/inbox")
def creator_inbox(
    url: str = Query(..., min_length=1, max_length=500),
    order: str = Query(default="relevance", pattern="^(relevance|time)$"),
    limit: int = Query(default=100, ge=1, le=300),
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
):
    mode = _normalize_account_mode(account_mode)
    api_key = _resolve_youtube_api_key(youtube_api_key, mode)
    video = _youtube_context_or_http_error(url.strip(), api_key)
    try:
        threads = fetch_video_comment_threads(video.video_id, api_key=api_key, order=order, limit=limit)
    except YouTubeConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    inbox = build_inbox(threads, channel_id=video.channel_id)
    return {
        "video": {
            "video_id": video.video_id,
            "url": video.url,
            "title": video.title,
            "channel": video.channel,
            "channel_id": video.channel_id,
            "thumbnail_url": video.thumbnail_url,
            "comment_count": video.comment_count,
        },
        "order": order,
        **inbox,
    }


def _optional_openai_client(api_key: str | None, model: str | None, mode: str) -> OpenAIResponsesClient | None:
    key = _normalize_openai_api_key(api_key)
    resolved_model = _normalize_openai_model(model)
    for env_prefix in (("DEMO_", "") if mode == "demo" else ("",)):
        key = key or _normalize_openai_api_key(os.getenv(f"{env_prefix}OPENAI_API_KEY"))
        resolved_model = resolved_model or _normalize_openai_model(os.getenv(f"{env_prefix}OPENAI_MODEL"))
    if not key or not resolved_model:
        return None
    return OpenAIResponsesClient(api_key=key, model=resolved_model)


@app.post("/creator/inbox/reply-drafts")
def creator_reply_drafts(
    payload: ReplyDraftRequest,
    openai_api_key: str | None = Header(default=None, alias="X-OpenAI-API-Key"),
    openai_model: str | None = Header(default=None, alias="X-OpenAI-Model"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
):
    mode = _normalize_account_mode(account_mode)
    return draft_replies(
        comment=payload.comment,
        category=payload.category,
        video_title=payload.video_title,
        client=_optional_openai_client(openai_api_key, openai_model, mode),
    )


from src.viewer.auto_replies import candidate_targets, verified_parent_comment, suggest_replies

class ViewerAutoReplySuggestRequest(BaseModel):
    video_id: str = Field(min_length=11, max_length=11, pattern=r"^[A-Za-z0-9_-]{11}$")
    parent_id: str = Field(min_length=5, max_length=100)


@app.get("/viewer/auto-replies/candidates", dependencies=[Depends(require_trusted_client)])
def viewer_auto_reply_candidates(
    url: str = Query(..., min_length=1, max_length=500),
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 YouTube 계정 연결이 필요합니다.")
    identity = _verified_account_channel(
        "personal", oauth_client_id, oauth_client_secret, oauth_redirect_uri,
    )
    key = _resolve_youtube_api_key(youtube_api_key, "personal")
    video = _youtube_context_or_http_error(url.strip(), key)
    try:
        threads = fetch_video_comment_threads(video.video_id, api_key=key, limit=40)
    except YouTubeLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "video": {"video_id": video.video_id, "title": video.title, "channel": video.channel},
        "items": candidate_targets(threads, viewer_channel_id=identity["channel_id"], limit=6),
        "scanned_count": len(threads),
    }


@app.post("/viewer/auto-replies/suggest", dependencies=[Depends(require_trusted_client)])
def viewer_auto_reply_suggest(
    payload: ViewerAutoReplySuggestRequest,
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    openai_api_key: str | None = Header(default=None, alias="X-OpenAI-API-Key"),
    openai_model: str | None = Header(default=None, alias="X-OpenAI-Model"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 YouTube 계정 연결이 필요합니다.")
    identity = _verified_account_channel(
        "personal", oauth_client_id, oauth_client_secret, oauth_redirect_uri,
    )
    client = _optional_openai_client(openai_api_key, openai_model, "personal")
    if client is None:
        raise HTTPException(status_code=503, detail="AI 대댓글 생성을 위해 OpenAI API Key와 모델을 설정해주세요.")
    key = _resolve_youtube_api_key(youtube_api_key, "personal")
    context = _youtube_context_or_http_error(
        f"https://www.youtube.com/watch?v={payload.video_id}", key
    )
    try:
        source = verified_parent_comment(
            parent_id=payload.parent_id, video_id=payload.video_id,
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
        if source.get("author_channel_id") == identity["channel_id"]:
            raise HTTPException(status_code=422, detail="본인 댓글에는 자동 대댓글을 추천하지 않습니다.")
        drafts = suggest_replies(
            comment=source["comment"], video_title=context.title,
            video_description=context.description or "", client=client,
        )
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (LLMNotReadyError, LLMGenerationError) as exc:
        raise _generation_http_error(exc) from exc
    return {"parent_id": payload.parent_id, "video_id": payload.video_id, "drafts": drafts}


@app.post("/viewer/replies", dependencies=[Depends(require_trusted_client)])
def viewer_reply_publish(
    payload: CreatorReplyRequest,
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(status_code=403, detail="개인 YouTube 계정 연결이 필요합니다.")
    if get_block_reason(payload.text) in {"profanity", "hate_speech", "threat", "spam"}:
        raise HTTPException(status_code=422, detail="안전 기준을 통과하지 못한 답글은 게시할 수 없습니다.")
    try:
        return publish_youtube_reply(
            parent_id=payload.parent_id, text=payload.text, require_video_owner=False,
            prevent_duplicate=True,
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
    except (YouTubeOAuthNotConfiguredError, YouTubeOAuthNotAuthorizedError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/creator/inbox/replies", dependencies=[Depends(require_trusted_client)])
def creator_reply_publish(
    payload: CreatorReplyRequest,
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
    oauth_redirect_uri: str | None = Header(default=None, alias="X-YouTube-OAuth-Redirect-URI"),
):
    if _normalize_account_mode(account_mode) != "personal":
        raise HTTPException(
            status_code=403,
            detail="데모 계정은 답글을 게시할 수 없습니다. 개인 계정에서 본인 YouTube 채널을 연결해주세요.",
        )
    if get_block_reason(payload.text) in {"profanity", "hate_speech", "threat", "spam"}:
        raise HTTPException(status_code=422, detail="안전 기준을 통과하지 못한 답글은 게시할 수 없습니다.")
    try:
        result = publish_youtube_reply(
            parent_id=payload.parent_id,
            text=payload.text,
            client_id=_normalize_oauth_client_id(oauth_client_id),
            client_secret=_normalize_oauth_client_secret(oauth_client_secret),
            redirect_uri=_normalize_oauth_redirect_uri(oauth_redirect_uri),
        )
        if result.get("reply_id") and result.get("video_id"):
            try:
                record_published_comment(
                    video_id=result["video_id"], comment_id=result["reply_id"],
                    comment=result.get("text") or payload.text,
                    comment_url=result.get("comment_url"), account_mode="personal",
                    owner_channel_id=authenticated_youtube_channel()["channel_id"],
                )
                return {**result, "tracked": True}
            except Exception:
                logger.exception("creator reply tracking failed")
        return {**result, "tracked": False,
                "tracking_warning": "답글 게시는 완료됐지만 추적 기록 저장에 실패했습니다."}
    except YouTubeOAuthNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeOAuthNotAuthorizedError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except YouTubeCommentPublishError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except YouTubeOAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/recommend/graph")
def recommend_comment_graph(
    request: RecommendRequest,
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    openai_api_key: str | None = Header(default=None, alias="X-OpenAI-API-Key"),
    openai_model: str | None = Header(default=None, alias="X-OpenAI-Model"),
):
    """Run LangGraph with request-scoped API credentials (never returned in output)."""
    if not request.youtube_url:
        raise HTTPException(status_code=422, detail="LangGraph 경로는 youtube_url이 필요합니다.")
    try:
        return comment_writer_graph.invoke({
            "video_url": request.youtube_url,
            "top_k": request.top_k,
            "additional_context": request.additional_context or "",
            "category_hint": request.category or "",
            "persona_id": request.persona_id,
            "youtube_api_key": _normalize_youtube_api_key(youtube_api_key) or "",
            "openai_api_key": _normalize_openai_api_key(openai_api_key) or "",
            "openai_model": _normalize_openai_model(openai_model) or "",
        })
    except InvalidYouTubeUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except YouTubeConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (LLMNotReadyError, LLMGenerationError, ModelNotReadyError) as exc:
        raise _generation_http_error(exc) from exc


@app.post("/score")
def score_comment_candidates(request: ScoreRequest):
    try:
        results = score_comments(post_text=request.post_text, comments=request.comments)
    except ModelNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"post_text": request.post_text, "results": results}


@app.post("/recommend")
def recommend_comment_candidates(
    request: RecommendRequest,
    youtube_api_key: str | None = Header(default=None, alias="X-YouTube-API-Key"),
    openai_api_key: str | None = Header(default=None, alias="X-OpenAI-API-Key"),
    openai_model: str | None = Header(default=None, alias="X-OpenAI-Model"),
    account_mode: str = Header(default="demo", alias="X-AI-Comment-Account-Mode"),
    private_history: str | None = Header(default=None, alias="X-AI-Comment-Private-History"),
):
    mode = _normalize_account_mode(account_mode)
    youtube_context = None
    source_parts: list[str] = []

    resolved_youtube_key = _normalize_youtube_api_key(youtube_api_key)
    if mode == "demo" and not resolved_youtube_key:
        resolved_youtube_key = _normalize_youtube_api_key(
            os.getenv("DEMO_YOUTUBE_API_KEY") or os.getenv("YOUTUBE_API_KEY")
        )

    if request.youtube_url and request.youtube_url.strip():
        youtube_context = _youtube_context_or_http_error(request.youtube_url.strip(), resolved_youtube_key)
        source_parts.append(build_reference_text(youtube_context))

    if request.post_text and request.post_text.strip():
        source_parts.append(request.post_text.strip())

    if not source_parts:
        raise HTTPException(status_code=422, detail="post_text 또는 youtube_url 중 하나는 필요합니다.")

    source_reference_text = "\n\n".join(source_parts)
    additional_context = request.additional_context.strip() if request.additional_context and request.additional_context.strip() else None
    generation_context = build_generation_context(
        source_reference_text,
        youtube_context=youtube_context,
        additional_context=additional_context,
        category_hint=request.category,
    )
    if request.persona_id.startswith("custom_"):
        if request.custom_persona is None or request.custom_persona.id != request.persona_id:
            raise HTTPException(status_code=422, detail="사용자 페르소나 설정이 선택한 ID와 일치하지 않습니다.")
        try:
            persona = build_custom_persona(request.custom_persona.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        if request.custom_persona is not None:
            raise HTTPException(status_code=422, detail="기존 페르소나 ID에 사용자 설정을 덮어쓸 수 없습니다.")
        persona = resolve_persona(request.persona_id)
        if request.persona_id != "none" and persona is None:
            raise HTTPException(status_code=422, detail="지원하지 않는 페르소나 ID입니다.")
    context_summary = summarize_generation_context(generation_context)
    resolved_category = str(context_summary["primary_category"] or "Other")
    ranking_reference_text = source_reference_text
    if additional_context:
        ranking_reference_text = f"{source_reference_text}\n\n추가 맥락: {additional_context}"

    request_openai_key = _normalize_openai_api_key(openai_api_key)
    request_openai_model = _normalize_openai_model(openai_model)
    if mode == "demo":
        request_openai_key = request_openai_key or _normalize_openai_api_key(
            os.getenv("DEMO_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        request_openai_model = request_openai_model or _normalize_openai_model(
            os.getenv("DEMO_OPENAI_MODEL") or os.getenv("OPENAI_MODEL")
        )
    generation_client = None
    active_llm = llm_readiness()
    if request_openai_key:
        resolved_model = request_openai_model
        if not resolved_model:
            raise HTTPException(
                status_code=503,
                detail="OpenAI 모델 설정이 필요합니다. 데모 계정은 DEMO_OPENAI_MODEL을 설정해주세요.",
            )
        generation_client = OpenAIResponsesClient(api_key=request_openai_key, model=resolved_model)
        active_llm = {
            "ready": True,
            "provider": "openai_responses_api",
            "selection": "request",
            "model": resolved_model,
            "missing": [],
        }

    try:
        ranked = recommend_comments_with_meta(
            ranking_reference_text,
            generation_context=generation_context,
            top_k=request.top_k,
            generation_client=generation_client,
            persona=persona,
        )
    except (LLMNotReadyError, LLMGenerationError, ModelNotReadyError) as exc:
        raise _generation_http_error(exc) from exc

    youtube_data = youtube_context.to_dict() if youtube_context else None
    source_type = "youtube" if youtube_context else "manual"
    source_text = youtube_context.title if youtube_context else (request.post_text or "").strip()
    if private_history == "1":
        # Logged-in users store private recommendations directly under Supabase RLS.
        # Never write their content into the legacy shared SQLite analysis history.
        analysis_id = "a_" + secrets.token_hex(8)
        stored_recommendations = [
            {**item, "id": "r_" + secrets.token_hex(8)}
            for item in ranked["recommendations"]
        ]
    else:
        analysis_id, stored_recommendations = save_analysis(
            source_type=source_type,
            source_text=source_text,
            category=resolved_category,
            recommendations=ranked["recommendations"],
            youtube_context=youtube_data,
            generation_context=generation_context,
            requested_count=request.top_k,
            additional_context=additional_context,
        )

    return {
        "analysis_id": analysis_id,
        "post_text": ranking_reference_text[:4_000],
        "resolved_category": resolved_category,
        "youtube_context": youtube_data,
        "context": context_summary,
        "recommendations": stored_recommendations,
        "generation": {
            "requested_count": request.top_k,
            "returned_count": len(stored_recommendations),
            "candidate_count": ranked["candidate_count"],
            "safe_candidate_count": ranked["safe_candidate_count"],
            "blocked_candidate_count": ranked["blocked_candidate_count"],
            "generator": "llm",
            "provider": active_llm.get("provider"),
            "model": active_llm.get("model"),
            "persona_id": persona.get("id") if persona else "none",
            "persona_name": persona.get("name") if persona else None,
        },
        "trace": ranked["trace"],
    }


@app.get("/analyses")
def recent_analyses(limit: int = Query(default=3, ge=1, le=30)):
    return {"items": list_analyses(limit=limit)}


@app.get("/analyses/{analysis_id}")
def analysis_detail(analysis_id: str):
    analysis = get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="분석 기록을 찾을 수 없습니다.")
    generation_context = analysis.get("generation_context")
    analysis["context_summary"] = summarize_generation_context(generation_context) if generation_context else None
    return analysis


@app.get("/comments")
def comments_list(
    query: str | None = Query(default=None, max_length=200),
    comment_type: str | None = Query(default=None, alias="type"),
    category: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return list_comments(
        query=query,
        comment_type=comment_type,
        category=category,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )


@app.get("/dashboard/summary")
def dashboard_kpis():
    return dashboard_summary()


@app.post("/recommendations/{recommendation_id}/feedback")
def recommendation_feedback(recommendation_id: str, request: FeedbackRequest):
    result = set_feedback(recommendation_id, useful=request.useful)
    if result is None:
        raise HTTPException(status_code=404, detail="추천 댓글을 찾을 수 없습니다.")
    return result


@app.get("/model/data-progress", dependencies=[Depends(require_trusted_client)])
def model_progress_overview():
    """Show real pre-LLM reference coverage and stored analysis growth."""
    return model_data_progress()
