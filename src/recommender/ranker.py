from __future__ import annotations

import logging
import math
import os
import re
import time
from difflib import SequenceMatcher

from src.llm.openai_client import LLMGenerationError
from src.model.predict import score_comments
from src.recommender.candidate_generator import CandidateGenerationClient, generate_candidates
from src.recommender.safety_filter import get_block_reason

logger = logging.getLogger(__name__)
MAX_GENERATION_ATTEMPTS = 3


def _time_budget_seconds() -> float:
    try:
        v = float(os.getenv("RECOMMEND_TIME_BUDGET_SECONDS", "90"))
        return v if v > 0 else 90.0
    except ValueError:
        return 90.0


def _normalized_comment(value: str) -> str:
    return " ".join(value.split()).strip().lower()



_LAUGHTER_MARKERS = re.compile(r"ㅋ{2,}|ㅎ{2,}|\b(?:lol|haha|hehe)\b", re.IGNORECASE)
_STYLE_PUNCTUATION = re.compile(r"[^\w가-힣]+")


def _has_laughter(text: str) -> bool:
    return bool(_LAUGHTER_MARKERS.search(text))


def _content_without_style(text: str) -> str:
    """Ignore trailing laughter and punctuation when comparing substantive text."""
    return _STYLE_PUNCTUATION.sub("", _LAUGHTER_MARKERS.sub("", text).lower())


def _too_similar(left: str, right: str) -> bool:
    a, b = _content_without_style(left), _content_without_style(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if min(len(a), len(b)) < 12:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.87


def _select_diverse_results(scored: list[dict], top_k: int, persona: dict | None) -> list[dict]:
    """Preserve ranker ordering but constrain repetitive laughter and near-paraphrases.

    Normal/default voice: at most 20% laughter-marked comments when alternatives
    exist. Playful persona: at most 40%. If a model outputs *only* marked or
    near-duplicate candidates, fill the rest rather than fail a working request.
    The raw model scores remain untouched and are NOT calibrated probabilities.
    """
    playful = (persona or {}).get("id") == "playful_casual"
    marker_limit = max(1, math.ceil(top_k * (0.4 if playful else 0.2)))
    chosen: list[dict] = []
    chosen_ids: set[str] = set()

    def add(allow_extra_laughter: bool, allow_similar: bool) -> None:
        for item in scored:
            if len(chosen) >= top_k:
                return
            comment = str(item["comment"])
            if comment in chosen_ids:
                continue
            if not allow_extra_laughter and _has_laughter(comment) and sum(
                _has_laughter(str(row["comment"])) for row in chosen
            ) >= marker_limit:
                continue
            if not allow_similar and any(_too_similar(comment, str(row["comment"])) for row in chosen):
                continue
            chosen.append(item)
            chosen_ids.add(comment)

    # First prioritize meaningful variation, then relax constraints if needed.
    add(allow_extra_laughter=False, allow_similar=False)
    add(allow_extra_laughter=False, allow_similar=True)
    add(allow_extra_laughter=True, allow_similar=False)
    add(allow_extra_laughter=True, allow_similar=True)
    return chosen[:top_k]


def recommend_comments_with_meta(
    post_text: str,
    *,
    generation_context: dict,
    top_k: int = 5,
    generation_client: CandidateGenerationClient | None = None,
    persona: dict | None = None,
) -> dict:
    safe_candidates: list[dict] = []
    seen_safe: set[str] = set()
    trace_candidates: list[dict] = []
    trace_by_normalized: dict[str, dict] = {}
    candidate_count = 0
    safety_blocked_count = 0
    duplicate_candidate_count = 0

    started_at = time.monotonic()
    time_budget = _time_budget_seconds()
    budget_exhausted = False
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        if attempt > 1 and time.monotonic() - started_at >= time_budget:
            budget_exhausted = True
            logger.warning("ranker.budget_exhausted attempt=%d safe=%d", attempt, len(safe_candidates))
            break
        candidates = generate_candidates(
            generation_context,
            minimum_count=max(top_k, 10),
            client=generation_client,
            persona=persona,
        )
        candidate_count += len(candidates)

        for candidate in candidates:
            comment = str(candidate.get("comment") or "")
            normalized = _normalized_comment(comment)
            block_reason = get_block_reason(comment)
            trace_item = {
                "sequence": len(trace_candidates) + 1,
                "attempt": attempt,
                "type": candidate.get("type", "general"),
                "comment": comment,
                "safety": "blocked" if block_reason else "passed",
                "safety_reason": block_reason,
                "duplicate": False,
                "ranker_score": None,
                "selected": False,
                "final_rank": None,
            }

            if block_reason is not None:
                safety_blocked_count += 1
                trace_candidates.append(trace_item)
                continue

            if not normalized or normalized in seen_safe:
                duplicate_candidate_count += 1
                trace_item["duplicate"] = True
                trace_candidates.append(trace_item)
                continue

            seen_safe.add(normalized)
            safe_candidates.append(candidate)
            trace_candidates.append(trace_item)
            trace_by_normalized[normalized] = trace_item

        logger.info("ranker.attempt attempt=%d generated=%d safe=%d elapsed_ms=%d",
                    attempt, len(candidates), len(safe_candidates),
                    int((time.monotonic()-started_at)*1000))
        if len(safe_candidates) >= top_k:
            break

    if len(safe_candidates) < top_k:
        raise LLMGenerationError(
            f"안전 필터 통과 후보가 부족합니다 ({len(safe_candidates)}/{top_k}). " + ("생성 시간 예산을 초과했습니다." if budget_exhausted else "새 후보 생성에 실패했습니다.")
        )

    comments = [item["comment"] for item in safe_candidates]
    scored_results = score_comments(post_text=post_text, comments=comments)
    comment_type_map = {
        item["comment"]: item.get("type", "general") for item in safe_candidates
    }

    selected_results = _select_diverse_results(scored_results, top_k, persona)
    recommendations = []
    for index, item in enumerate(selected_results, start=1):
        recommendations.append(
            {
                "rank": index,
                "type": comment_type_map.get(item["comment"], "general"),
                "comment": item["comment"],
                "predicted_score": item["score"],
            }
        )

    final_rank_by_normalized = {
        _normalized_comment(item["comment"]): index
        for index, item in enumerate(selected_results, start=1)
    }
    score_by_normalized = {
        _normalized_comment(item["comment"]): item["score"]
        for item in scored_results
    }
    for normalized, trace_item in trace_by_normalized.items():
        trace_item["ranker_score"] = score_by_normalized.get(normalized)
        final_rank = final_rank_by_normalized.get(normalized)
        trace_item["selected"] = final_rank is not None
        trace_item["final_rank"] = final_rank

    return {
        "recommendations": recommendations,
        "candidate_count": candidate_count,
        "safe_candidate_count": len(safe_candidates),
        "blocked_candidate_count": candidate_count - len(safe_candidates),
        "trace": {
            "safety_blocked_count": safety_blocked_count,
            "duplicate_candidate_count": duplicate_candidate_count,
            "candidates": trace_candidates,
        },
    }


def recommend_comments(
    post_text: str,
    *,
    generation_context: dict,
    top_k: int = 5,
    generation_client: CandidateGenerationClient | None = None,
    persona: dict | None = None,
) -> list[dict]:
    return recommend_comments_with_meta(
        post_text,
        generation_context=generation_context,
        top_k=top_k,
        generation_client=generation_client,
        persona=persona,
    )["recommendations"]
