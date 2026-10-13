"""Measured comment samples vs generated reply *candidates*, not audience probabilities.

Deterministic, inspectable intent labels are deliberately heuristic. Never call the
distance between these two distributions model accuracy: samples are not unbiased,
and generated candidates do not represent randomly sampled audience responses.
"""
from __future__ import annotations

import re

INTENTS = (
    ("question", "질문"),
    ("praise", "칭찬"),
    ("confusion", "혼란"),
    ("complaint", "불만"),
    ("purchase", "구매 의도"),
    ("risk", "리스크"),
    ("other", "기타"),
)
PATTERNS = {
    "risk": re.compile(r"사기|거짓|조작|불법|혐오|신고|논란|위험|허위|과장광고|환불|저작권", re.I),
    "purchase": re.compile(r"구매|구입|사고 싶|살까|사야|가격|얼마|출시|재입고|어디서 사|링크 있|예약", re.I),
    "complaint": re.compile(r"별로|아쉽|실망|불편|비싸|싫|최악|왜 이렇게|문제 있|개선|답답", re.I),
    "confusion": re.compile(r"무슨 뜻|이해가 안|이해 안|헷갈|모르겠|차이가 뭐|어떤 의미|설명이 부족|왜 그런", re.I),
    "question": re.compile(r"궁금|어떻게|왜 |뭐가|언제|어디|누가|인가요|나요\b|까요\b", re.I),
    "praise": re.compile(r"감사|고마|최고|좋아요|좋네요|잘\s*봤|잘봤|응원|유익|도움|재밌|재미있|멋지|대박|힐링|만족", re.I),
}

def classify_intent(text: str, comment_type: str | None = None) -> str:
    content = (text or "").strip()
    if not content:
        return "other"
    for intent in ("risk", "purchase", "complaint", "confusion"):
        if PATTERNS[intent].search(content):
            return intent
    if comment_type == "negative":
        return "complaint"
    if "?" in content or "？" in content or comment_type == "question" or PATTERNS["question"].search(content):
        return "question"
    if comment_type in {"empathy", "insight"} or PATTERNS["praise"].search(content):
        return "praise"
    return "other"


def classify_observed(threads: list[dict]) -> list[dict]:
    seen: set[str] = set()
    items = []
    for item in threads[:100]:
        text = str(item.get("text") or "").strip()[:1200]
        identifier = str(item.get("id") or "")
        if not text or not identifier or identifier in seen:
            continue
        seen.add(identifier)
        items.append({
            "id": identifier,
            "text": text,
            "intent": classify_intent(text),
            "like_count": max(0, int(item.get("like_count") or 0)),
            "reply_count": max(0, int(item.get("reply_count") or 0)),
            "published_at": item.get("published_at"),
        })
    return items


def summarize_intents(items: list[dict]) -> dict:
    counts = {key: 0 for key, _ in INTENTS}
    for item in items:
        intent = item.get("intent") or "other"
        counts[intent if intent in counts else "other"] += 1
    total = sum(counts.values())
    distribution = [
        {"key": key, "label": label, "count": counts[key], "percentage": round(100 * counts[key] / total, 1) if total else 0.0}
        for key, label in INTENTS
    ]
    return {"total": total, "distribution": distribution}


def classify_expected(recommendations: list[dict]) -> list[dict]:
    # Only selected saved Top-K generated recommendations; no trace-only candidates
    # that were never stored and no invented percentages.
    return [
        {"intent": classify_intent(str(item.get("comment") or ""), str(item.get("type") or "")),
         "text": str(item.get("comment") or "")}
        for item in recommendations if str(item.get("comment") or "").strip()
    ]


def compare_distributions(expected: dict, observed: dict) -> dict:
    ex = {item["key"]: item["percentage"] for item in expected["distribution"]}
    ob = {item["key"]: item["percentage"] for item in observed["distribution"]}
    rows = [
        {"key": key, "label": label, "expected_percentage": ex.get(key, 0.0),
         "observed_percentage": ob.get(key, 0.0),
         "delta_percentage_points": round(ob.get(key, 0.0) - ex.get(key, 0.0), 1)}
        for key, label in INTENTS
    ]
    return {
        "distribution": rows,
        "sample_difference_points": round(sum(abs(row["delta_percentage_points"]) for row in rows) / 2, 1),
        "method": "generated_top_k_vs_public_comment_sample",
        "warning": "생성된 후보와 YouTube API로 조회한 공개 댓글 표본을 비교한 수치입니다. 예측 확률·정확도나 전체 시청자의 실제 성향을 의미하지 않습니다.",
    }


def build_observation_report(video_id: str, threads: list[dict], recommendations: list[dict] | None = None) -> dict:
    comments = classify_observed(threads)
    actual = summarize_intents(comments)
    expected = summarize_intents(classify_expected(recommendations or [])) if recommendations is not None else None
    examples = sorted(comments, key=lambda item: (-item["like_count"], -item["reply_count"]))[:8]
    return {
        "video_id": video_id,
        "order": "relevance",
        "observed": actual,
        "expected": expected,
        "comparison": compare_distributions(expected, actual) if expected and expected["total"] and actual["total"] else None,
        "examples": examples,
        "comments": comments,
        "caveat": "공개 최상위 댓글 최대 100건의 편향된 표본입니다. 관련도순 수집이므로 시청자 전체의 비율이나 시간대별 반응으로 해석하지 마세요.",
    }
