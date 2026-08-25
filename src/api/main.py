from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.schemas import RecommendRequest, ScoreRequest
from src.model.predict import score_comments
from src.recommender.ranker import recommend_comments
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
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "AI Comment Recommender API is running",
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
    results = score_comments(
        post_text=request.post_text,
        comments=request.comments,
    )

    return {
        "post_text": request.post_text,
        "results": results,
    }


@app.post("/recommend")
def recommend_comment_candidates(request: RecommendRequest):
    youtube_context = None
    reference_parts: list[str] = []

    if request.youtube_url:
        youtube_context = _youtube_context_or_http_error(request.youtube_url)
        reference_parts.append(build_reference_text(youtube_context))

    if request.post_text and request.post_text.strip():
        reference_parts.append(request.post_text.strip())

    if not reference_parts:
        raise HTTPException(
            status_code=422,
            detail="post_text 또는 youtube_url 중 하나는 필요합니다.",
        )

    reference_text = "\n\n".join(reference_parts)
    recommendations = recommend_comments(
        post_text=reference_text,
        top_k=request.top_k,
    )

    return {
        "post_text": reference_text,
        "youtube_context": youtube_context.to_dict() if youtube_context else None,
        "recommendations": recommendations,
    }
