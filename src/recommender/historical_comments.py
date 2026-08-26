from __future__ import annotations

import csv
import math
import re
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Iterable

from src.config import BASE_DIR

DEFAULT_DATASET_PATHS = (
    BASE_DIR / "data" / "raw" / "social_issues_comments.csv",
    BASE_DIR / "data" / "raw" / "vlog_comments.csv",
)

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9+#.-]{2,}")
_QUESTION_RE = re.compile(r"[?？]|(궁금|어떻게|왜 |뭐가|무엇|언제|어디)")
_CASUAL_RE = re.compile(r"ㅋㅋ|ㅎㅎ|lol|LOL|ㅠㅠ|ㅜㅜ|😊|😂|🤣")


def _tokens(text: str) -> set[str]:
    return {token.lower().strip(".-") for token in _TOKEN_RE.findall(text or "") if len(token.strip(".-")) >= 2}


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=8)
def _load_dataset(path_text: str) -> tuple[dict, ...]:
    path = Path(path_text)
    if not path.exists():
        return ()

    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                comment = (raw.get("comment_text") or "").strip()
                if not comment or len(comment) > 200:
                    continue
                rows.append(
                    {
                        "post_text": (raw.get("post_text") or "").strip(),
                        "comment_text": comment,
                        "category": (raw.get("category") or path.stem.replace("_comments", "")).strip(),
                        "like_count": _as_int(raw.get("like_count")),
                        "reply_count": _as_int(raw.get("reply_count")),
                        "is_top_comment": _as_int(raw.get("is_top_comment")),
                    }
                )
    except OSError:
        return ()
    return tuple(rows)


def _dataset_bias(topics: Iterable[str], content_styles: Iterable[str]) -> tuple[str, ...]:
    topic_set = {item.lower() for item in topics}
    style_set = {item.lower() for item in content_styles}
    vlog_topics = {"travel", "food", "beauty", "fashion", "fitness", "lifestyle", "shopping", "relationships"}
    social_topics = {"ai", "software", "career", "education", "finance", "economy", "politics", "law", "science", "technology"}
    if "vlog" in style_set or topic_set & vlog_topics:
        return ("vlog",)
    if topic_set & social_topics or style_set & {"news", "discussion", "commentary", "interview", "educational"}:
        return ("social_issues",)
    return ("social_issues", "vlog")


def _percentile(sorted_values: list[int], fraction: float) -> int:
    if not sorted_values:
        return 0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return round(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight)


def build_historical_profile(
    reference_text: str,
    *,
    topics: Iterable[str] = (),
    content_styles: Iterable[str] = (),
    dataset_paths: Iterable[str | Path] | None = None,
    profile_limit: int = 80,
    reference_limit: int = 6,
) -> dict:
    """Select relevant historical comments and summarize response-shape signals in code.

    The current repository only contains social_issues/vlog datasets. This retriever
    exposes that coverage explicitly instead of claiming full YouTube-category support.
    """
    paths = tuple(Path(path) for path in (dataset_paths or DEFAULT_DATASET_PATHS))
    preferred = set(_dataset_bias(topics, content_styles))
    query_tokens = _tokens(reference_text)

    scored: list[tuple[float, dict]] = []
    available_categories: set[str] = set()
    for path in paths:
        for row in _load_dataset(str(path)):
            category = row["category"] or path.stem.replace("_comments", "")
            available_categories.add(category)
            row_tokens = _tokens(f"{row['post_text']} {row['comment_text']}")
            overlap = len(query_tokens & row_tokens)
            score = float(overlap * 3)
            if category in preferred:
                score += 2.0
            if row["is_top_comment"]:
                score += 4.0
            score += min(2.0, math.log10(max(1, row["like_count"] + 1)) * 0.5)
            if score > 0:
                scored.append((score, row))

    scored.sort(key=lambda item: (item[0], item[1]["like_count"], item[1]["reply_count"]), reverse=True)
    selected = [row for _, row in scored[:profile_limit]]

    if not selected:
        return {
            "coverage": "none",
            "available_categories": sorted(available_categories),
            "matched_count": 0,
            "preferred_length": [20, 80],
            "median_length": 0,
            "question_ratio": 0.0,
            "casual_ratio": 0.0,
            "reference_examples": [],
        }

    lengths = sorted(len(row["comment_text"]) for row in selected)
    question_ratio = sum(bool(_QUESTION_RE.search(row["comment_text"])) for row in selected) / len(selected)
    casual_ratio = sum(bool(_CASUAL_RE.search(row["comment_text"])) for row in selected) / len(selected)

    references: list[str] = []
    seen: set[str] = set()
    for row in selected:
        text = row["comment_text"].strip()
        normalized = re.sub(r"\s+", " ", text).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        references.append(text)
        if len(references) >= reference_limit:
            break

    covered_categories = {row["category"] for row in selected if row["category"]}
    coverage = "matched_legacy_category" if covered_categories & preferred else "cross_category_reference"
    return {
        "coverage": coverage,
        "available_categories": sorted(available_categories),
        "matched_categories": sorted(covered_categories),
        "matched_count": len(selected),
        "preferred_length": [_percentile(lengths, 0.25), _percentile(lengths, 0.75)],
        "median_length": int(median(lengths)),
        "question_ratio": round(question_ratio, 3),
        "casual_ratio": round(casual_ratio, 3),
        "reference_examples": references,
    }
