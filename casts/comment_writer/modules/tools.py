"""Adapters around the existing product pipeline; domain code does not depend on LangGraph."""
from src.youtube.context import fetch_youtube_context, build_reference_text
from src.recommender.generation_context import build_generation_context, summarize_generation_context
from src.recommender.safety_filter import get_block_reason
from src.model.predict import score_comments
from src.recommender.candidate_generator import generate_candidates


def collect_video_context(video_url: str, *, additional_context: str | None = None, category_hint: str | None = None, youtube_api_key: str | None = None) -> dict:
    video = fetch_youtube_context(video_url, api_key=youtube_api_key)
    source = build_reference_text(video)
    extra = (additional_context or "").strip() or None
    context = build_generation_context(source, youtube_context=video, additional_context=extra, category_hint=category_hint)
    return {
        "video_id": video.video_id,
        "post_text": source + ("\n\n추가 맥락: " + extra if extra else ""),
        "generation_context": context,
        "context_summary": summarize_generation_context(context),
        "youtube_context": video.to_dict(),
    }


def generate_comment_candidates(generation_context: dict, *, candidate_count: int) -> list[dict]:
    return generate_candidates(generation_context, minimum_count=candidate_count)


def check_comment_safety(comment: str) -> dict:
    reason = get_block_reason(comment)
    return {"safe": reason is None, "reason": reason}


def score_comment_candidates(post_text: str, comments: list[str]) -> list[dict]:
    return score_comments(post_text=post_text, comments=comments)
