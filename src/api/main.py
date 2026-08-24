from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.api.schemas import RecommendRequest, ScoreRequest
from src.model.predict import score_comments
from src.recommender.ranker import recommend_comments

app = FastAPI(
    title="AI Comment Recommender",
    description="댓글 좋아요 반응 예측 기반 AI 댓글 추천 시스템",
    version="0.2.0",
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
    recommendations = recommend_comments(
        post_text=request.post_text,
        top_k=request.top_k,
    )

    return {
        "post_text": request.post_text,
        "recommendations": recommendations,
    }
