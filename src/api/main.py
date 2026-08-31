from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.schemas import FeedbackRequest, RecommendRequest, ScoreRequest
from src.llm.openai_client import LLMGenerationError, LLMNotReadyError
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
        "youtube": {"configured": bool(os.getenv("YOUTUBE_API_KEY"))},
        "storage": {"ready": True},
    }


def _youtube_context_or_http_error(url: str):
    try:
        return fetch_youtube_context(url)
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
def preview_youtube_video(url: str = Query(..., min_length=1)):
    return _youtube_context_or_http_error(url).to_dict()


@app.post("/score")
def score_comment_candidates(request: ScoreRequest):
    try:
        results = score_comments(post_text=request.post_text, comments=request.comments)
    except ModelNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"post_text": request.post_text, "results": results}


@app.post("/recommend")
def recommend_comment_candidates(request: RecommendRequest):
    youtube_context = None
    source_parts: list[str] = []

    if request.youtube_url and request.youtube_url.strip():
        youtube_context = _youtube_context_or_http_error(request.youtube_url.strip())
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

    try:
        ranked = recommend_comments_with_meta(
            ranking_reference_text,
            generation_context=generation_context,
            top_k=request.top_k,
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

    active_llm = llm_readiness()
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
