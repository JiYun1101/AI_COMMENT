"""
안전 필터 v1(기존 키워드 8개) vs v2(규칙 고도화) 비교 평가 스크립트.

data/raw/*_comments.csv 실데이터에 대해 두 버전의 필터를 각각 적용해
차단율과 차단 사유 분포를 비교한다.

Usage:
    python scripts/evaluate_safety_filter.py
"""

from collections import Counter
from pathlib import Path

import pandas as pd

from src.recommender.safety_filter import get_block_reason

ROOT = Path(__file__).resolve().parent.parent

OLD_BLOCKED_KEYWORDS = [
    "죽어", "꺼져", "멍청", "병신", "혐오", "최악", "개새", "닥쳐",
]


def is_safe_v1(text: str) -> bool:
    if not text:
        return False
    t = str(text).strip()
    if len(t) < 5 or len(t) > 200:
        return False
    return not any(kw in t for kw in OLD_BLOCKED_KEYWORDS)


def evaluate(path: Path, category: str):
    df = pd.read_csv(path)
    df["comment_text"] = df["comment_text"].fillna("").astype(str)

    v1_blocked = ~df["comment_text"].apply(is_safe_v1)
    reasons = df["comment_text"].apply(get_block_reason)
    v2_blocked = reasons.notna()

    print(f"=== {category} (n={len(df)}) ===")
    print(f"  v1 (기존) 차단율: {v1_blocked.mean()*100:.2f}% ({v1_blocked.sum()}건)")
    print(f"  v2 (개선) 차단율: {v2_blocked.mean()*100:.2f}% ({v2_blocked.sum()}건)")
    print(f"  v1 통과 -> v2 신규 차단: {((~v1_blocked) & v2_blocked).sum()}건")

    reason_counts = Counter(reasons.dropna())
    print("  v2 차단 사유 분포:")
    for reason, cnt in reason_counts.most_common():
        print(f"    - {reason}: {cnt}")
    print()


def main():
    for category in ("social_issues", "vlog"):
        evaluate(ROOT / "data" / "raw" / f"{category}_comments.csv", category)


if __name__ == "__main__":
    main()
