from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from src.api.schemas import RecommendRequest, ScoreRequest
from src.recommender.ranker import recommend_comments
from src.model.predict import score_comments

app = FastAPI(
    title="AI Comment Recommender",
    description="댓글 좋아요 반응 예측 기반 AI 댓글 추천 시스템",
    version="0.1.0",
)


@app.get("/")
def root():
    """루트 경로는 Swagger 문서로 리다이렉트해 바로 테스트 가능하도록 한다."""
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