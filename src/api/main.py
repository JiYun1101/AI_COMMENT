from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.schemas import FeedbackRequest, RecommendRequest, ScoreRequest
from src.model.predict import ModelNotReadyError, model_readiness, score_comments
from src.recommender.candidate_generator import infer_category
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
    description="댓글 좋아요 반응 예측 기반 AI 댓글 추천 시스템",
    version="0.4.0",
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
    readiness = model_readiness()
    return {
        "status": "ok" if readiness["ready"] else "degraded",
        "message": "AI Comment Recommender API is running",
        "model": readiness,
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
    reference_parts: list[str] = []

    if request.youtube_url and request.youtube_url.strip():
        youtube_context = _youtube_context_or_http_error(request.youtube_url.strip())
        reference_parts.append(build_reference_text(youtube_context))

    if request.post_text and request.post_text.strip():
        reference_parts.append(request.post_text.strip())

    if request.additional_context and request.additional_context.strip():
        reference_parts.append(f"추가 맥락: {request.additional_context.strip()}")

    if not reference_parts:
        raise HTTPException(status_code=422, detail="post_text 또는 youtube_url 중 하나는 필요합니다.")

    reference_text = "\n\n".join(reference_parts)
    resolved_category = infer_category(reference_text) if request.category == "auto" else request.category

    try:
        ranked = recommend_comments_with_meta(
            reference_text,
            top_k=request.top_k,
            category=resolved_category,
        )
    except ModelNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    youtube_data = youtube_context.to_dict() if youtube_context else None
    source_type = "youtube" if youtube_context else "manual"
    source_text = youtube_context.title if youtube_context else (request.post_text or request.additional_context or "").strip()
    analysis_id, stored_recommendations = save_analysis(
        source_type=source_type,
        source_text=source_text,
        category=resolved_category,
        recommendations=ranked["recommendations"],
        youtube_context=youtube_data,
    )

    return {
        "analysis_id": analysis_id,
        "post_text": reference_text[:4_000],
        "resolved_category": resolved_category,
        "youtube_context": youtube_data,
        "recommendations": stored_recommendations,
        "generation": {
            "requested_count": request.top_k,
            "returned_count": len(stored_recommendations),
            "candidate_count": ranked["candidate_count"],
            "safe_candidate_count": ranked["safe_candidate_count"],
            "blocked_candidate_count": ranked["blocked_candidate_count"],
        },
    }


@app.get("/analyses")
def recent_analyses(limit: int = Query(default=3, ge=1, le=30)):
    return {"items": list_analyses(limit=limit)}


@app.get("/analyses/{analysis_id}")
def analysis_detail(analysis_id: str):
    analysis = get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="분석 기록을 찾을 수 없습니다.")
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
