import re
from pathlib import Path

import pandas as pd

from src.config import BASE_DIR


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_processed.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"


URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+")


CASUAL_KEYWORDS = [
    "ㅋㅋ",
    "ㅎㅎ",
    "진짜",
    "완전",
    "대박",
    "와",
    "헐",
    "ㄹㅇ",
]

EMPATHY_KEYWORDS = [
    "공감",
    "와닿",
    "맞아요",
    "저도",
    "나도",
    "진짜",
    "그렇죠",
    "이해",
]

INSIGHT_KEYWORDS = [
    "핵심",
    "결국",
    "중요",
    "관점",
    "설계",
    "정의",
    "본질",
    "방향",
    "구조",
    "문제 정의",
]

CRITICISM_KEYWORDS = [
    "별로",
    "문제다",
    "아쉽",
    "비판",
    "틀렸",
    "최악",
    "이상하다",
    "불편",
]


def count_keywords(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def tokenize_text(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()

    tokens = TOKEN_PATTERN.findall(text.lower())

    return {
        token
        for token in tokens
        if len(token) >= 2
    }


def calculate_context_features(post_text: str, comment_text: str) -> dict:
    post_tokens = tokenize_text(post_text)
    comment_tokens = tokenize_text(comment_text)

    if not post_tokens or not comment_tokens:
        return {
            "post_comment_overlap_count": 0,
            "post_comment_jaccard": 0.0,
            "post_comment_coverage": 0.0,
            "post_comment_length_ratio": 0.0,
        }

    intersection = post_tokens & comment_tokens
    union = post_tokens | comment_tokens

    post_length = max(len(str(post_text)), 1)
    comment_length = len(str(comment_text))

    return {
        "post_comment_overlap_count": len(intersection),
        "post_comment_jaccard": len(intersection) / len(union),
        "post_comment_coverage": len(intersection) / len(post_tokens),
        "post_comment_length_ratio": comment_length / post_length,
    }


def extract_text_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["post_text"] = df["post_text"].fillna("").astype(str)
    df["comment_text"] = df["comment_text"].fillna("").astype(str)

    df["comment_length"] = df["comment_text"].str.len()
    df["word_count"] = df["comment_text"].apply(lambda x: len(x.split()))

    df["sentence_count"] = df["comment_text"].apply(
        lambda x: max(1, x.count(".") + x.count("!") + x.count("?"))
    )

    df["question_count"] = df["comment_text"].str.count(r"\?")
    df["exclamation_count"] = df["comment_text"].str.count("!")

    df["laugh_count"] = df["comment_text"].apply(
        lambda x: x.count("ㅋㅋ") + x.count("ㅎㅎ")
    )

    df["sad_count"] = df["comment_text"].apply(
        lambda x: (
            x.count("ㅠㅠ")
            + x.count("ㅜㅜ")
            + x.count("ㅠ")
            + x.count("ㅜ")
        )
    )

    df["has_question"] = (df["question_count"] > 0).astype(int)

    df["has_url"] = df["comment_text"].apply(
        lambda x: int(bool(URL_PATTERN.search(x)))
    )

    df["has_number"] = df["comment_text"].apply(
        lambda x: int(any(char.isdigit() for char in x))
    )

    df["casual_score"] = df["comment_text"].apply(
        lambda x: count_keywords(x, CASUAL_KEYWORDS)
    )

    df["empathy_score"] = df["comment_text"].apply(
        lambda x: count_keywords(x, EMPATHY_KEYWORDS)
    )

    df["insight_score"] = df["comment_text"].apply(
        lambda x: count_keywords(x, INSIGHT_KEYWORDS)
    )

    df["criticism_score"] = df["comment_text"].apply(
        lambda x: count_keywords(x, CRITICISM_KEYWORDS)
    )

    context_features = df.apply(
        lambda row: calculate_context_features(
            row["post_text"],
            row["comment_text"],
        ),
        axis=1,
    )

    context_features_df = pd.DataFrame(
        context_features.tolist(),
        index=df.index,
    )

    df = pd.concat([df, context_features_df], axis=1)

    return df


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    required_columns = ["post_text", "comment_text"]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {missing_columns}")

    df = extract_text_features(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"텍스트 피처 추출 완료: {OUTPUT_PATH}")
    print("shape:", df.shape)
    print()

    preview_columns = [
        "post_id",
        "comment_id",
        "comment_text",
        "is_top_comment",
        "comment_length",
        "insight_score",
        "empathy_score",
        "criticism_score",
        "post_comment_overlap_count",
        "post_comment_jaccard",
        "post_comment_coverage",
        "post_comment_length_ratio",
    ]

    available_preview_columns = [
        column
        for column in preview_columns
        if column in df.columns
    ]

    print(df[available_preview_columns].head())

    if "category" in df.columns:
        print()
        print("카테고리 분포")
        print(df["category"].value_counts())

    if "is_top_comment" in df.columns:
        print()
        print("라벨 분포")
        print(df["is_top_comment"].value_counts())


if __name__ == "__main__":
    main()