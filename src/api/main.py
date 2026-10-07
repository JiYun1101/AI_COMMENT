from __future__ import annotations

import html
import os

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

from src.api.schemas import FeedbackRequest, RecommendRequest, ScoreRequest, YouTubeCommentPublishRequest
from src.llm.openai_client import LLMGenerationError, LLMNotReadyError, OpenAIResponsesClient
from src.llm.provider import llm_readiness
from src.model.predict import ModelNotReadyError, model_readiness, score_comments
from src.recommender.generation_context import build_generation_context, summarize_generation_context
from src.recommender.ranker import recommend_comments_with_meta
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
    youtube_oauth_status,
)
from src.youtube.demo import (
    DemoYouTubeNotConfiguredError,
    DemoYouTubeRateLimitError,
    demo_status,
    demo_visitor_key,
    publish_demo_youtube_comment,
)
from src.youtube.context import (
    InvalidYouTubeUrlError,
    YouTubeConfigurationError,
    YouTubeLookupError,
    build_reference_text,
    fetch_youtube_context,
)

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


@app.get("/health")
def health_check():
    model = model_readiness()
    llm = llm_readiness()
    return {
        "status": "ok" if model["ready"] and llm["ready"] else "degraded",
        "message": "AI Comment Recommender API is running",
        "model": model,
        "llm": llm,
        "youtube": {
            "configured": bool(os.getenv("YOUTUBE_API_KEY")),
            "oauth": youtube_oauth_status(),
            "demo": demo_status(),
        },
        "storage": {"ready": True},
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
):
    return _youtube_context_or_http_error(url, youtube_api_key).to_dict()


@app.get("/youtube/oauth/status")
def youtube_oauth_connection_status(
    oauth_client_id: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-ID"),
    oauth_client_secret: str | None = Header(default=None, alias="X-YouTube-OAuth-Client-Secret"),
):
    return youtube_oauth_status(
        client_id=_normalize_oauth_client_id(oauth_client_id),
        client_secret=_normalize_oauth_client_secret(oauth_client_secret),
    )


@app.get("/youtube/oauth/start")
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


@app.post("/youtube/oauth/disconnect")
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
    normalized_mode = (account_mode or "demo").strip().lower()
    if normalized_mode not in {"demo", "personal"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 계정 모드입니다.")

    if normalized_mode == "demo":
        visitor_key = demo_visitor_key(_request_identity(request))
        try:
            return publish_demo_youtube_comment(
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

    try:
        return publish_youtube_comment(
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
):
    youtube_context = None
    source_parts: list[str] = []

    if request.youtube_url and request.youtube_url.strip():
        youtube_context = _youtube_context_or_http_error(request.youtube_url.strip(), youtube_api_key)
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
    context_summary = summarize_generation_context(generation_context)
    resolved_category = str(context_summary["primary_category"] or "Other")
    ranking_reference_text = source_reference_text
    if additional_context:
        ranking_reference_text = f"{source_reference_text}\n\n추가 맥락: {additional_context}"

    request_openai_key = _normalize_openai_api_key(openai_api_key)
    request_openai_model = _normalize_openai_model(openai_model)
    generation_client = None
    active_llm = llm_readiness()
    if request_openai_key:
        resolved_model = request_openai_model or "gpt-5.6-luna"
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
        )
    except (LLMNotReadyError, LLMGenerationError, ModelNotReadyError) as exc:
        raise _generation_http_error(exc) from exc

    youtube_data = youtube_context.to_dict() if youtube_context else None
    source_type = "youtube" if youtube_context else "manual"
    source_text = youtube_context.title if youtube_context else (request.post_text or "").strip()
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
