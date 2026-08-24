import re

import pandas as pd

from src.config import BASE_DIR


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_processed.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"

URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+")

CASUAL_KEYWORDS = [
    "ㅋㅋ", "ㅎㅎ", "진짜", "완전", "대박", "와", "헐", "ㄹㅇ",
]
EMPATHY_KEYWORDS = [
    "공감", "와닿", "맞아요", "저도", "나도", "진짜", "그렇죠", "이해",
]
INSIGHT_KEYWORDS = [
    "핵심", "결국", "중요", "관점", "설계", "정의", "본질", "방향",
    "구조", "문제 정의",
]
CRITICISM_KEYWORDS = [
    "별로", "문제다", "아쉽", "비판", "틀렸", "최악", "이상하다", "불편",
]

KOREAN_PARTICLES = [
    "으로부터", "으로서", "으로써", "에게서", "한테서", "에서는", "에서",
    "에게", "한테", "으로", "라고", "처럼", "보다", "부터", "까지", "마다",
    "조차", "마저", "밖에", "이나", "이랑", "하고", "와", "과", "은", "는",
    "이", "가", "을", "를", "에", "의", "도", "만", "로", "나", "랑",
]

TEXT_FEATURE_COLUMNS = [
    "comment_length",
    "word_count",
    "sentence_count",
    "question_count",
    "exclamation_count",
    "laugh_count",
    "sad_count",
    "has_question",
    "has_url",
    "has_number",
    "casual_score",
    "empathy_score",
    "insight_score",
    "criticism_score",
]

CONTEXT_FEATURE_COLUMNS = [
    "post_comment_overlap_count",
    "post_comment_jaccard",
    "post_comment_coverage",
    "post_comment_length_ratio",
]


def count_keywords(text: str, keywords: list[str]) -> int:
    return sum(text.count(keyword) for keyword in keywords)


def extract_comment_features(comment: str | None) -> dict:
    text = str(comment or "")

    question_count = text.count("?")
    exclamation_count = text.count("!")
    sentence_count = max(1, len(re.findall(r"[.!?。！？]+", text)))

    return {
        "comment_length": len(text),
        "word_count": len(text.split()),
        "sentence_count": sentence_count,
        "question_count": question_count,
        "exclamation_count": exclamation_count,
        "laugh_count": text.count("ㅋㅋ") + text.count("ㅎㅎ"),
        "sad_count": text.count("ㅠㅠ") + text.count("ㅜㅜ"),
        "has_question": int(question_count > 0),
        "has_url": int(bool(URL_PATTERN.search(text))),
        "has_number": int(any(char.isdigit() for char in text)),
        "casual_score": count_keywords(text, CASUAL_KEYWORDS),
        "empathy_score": count_keywords(text, EMPATHY_KEYWORDS),
        "insight_score": count_keywords(text, INSIGHT_KEYWORDS),
        "criticism_score": count_keywords(text, CRITICISM_KEYWORDS),
    }


def normalize_token(token: str) -> str:
    token = token.lower().strip()

    for particle in KOREAN_PARTICLES:
        if token.endswith(particle) and len(token) > len(particle) + 1:
            return token[: -len(particle)]

    return token


def tokenize_text(text: str | None) -> set[str]:
    raw_tokens = TOKEN_PATTERN.findall(str(text or "").lower())
    tokens = {normalize_token(token) for token in raw_tokens}
    return {token for token in tokens if len(token) >= 2}


def calculate_context_features(
    post_text: str | None,
    comment_text: str | None,
) -> dict:
    post = str(post_text or "")
    comment = str(comment_text or "")
    post_tokens = tokenize_text(post)
    comment_tokens = tokenize_text(comment)

    if not post_tokens or not comment_tokens:
        return {
            "post_comment_overlap_count": 0,
            "post_comment_jaccard": 0.0,
            "post_comment_coverage": 0.0,
            "post_comment_length_ratio": 0.0,
        }

    intersection = post_tokens & comment_tokens
    union = post_tokens | comment_tokens

    return {
        "post_comment_overlap_count": len(intersection),
        "post_comment_jaccard": len(intersection) / len(union),
        "post_comment_coverage": len(intersection) / len(post_tokens),
        "post_comment_length_ratio": len(comment) / max(len(post), 1),
    }


def extract_feature_row(
    post_text: str | None,
    comment_text: str | None,
) -> dict:
    features = extract_comment_features(comment_text)
    features.update(calculate_context_features(post_text, comment_text))
    return features


def extract_text_features(df: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [
        column
        for column in ("post_text", "comment_text")
        if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {missing_columns}")

    result = df.copy()
    rows = [
        extract_feature_row(post_text, comment_text)
        for post_text, comment_text in zip(
            result["post_text"],
            result["comment_text"],
        )
    ]
    feature_df = pd.DataFrame(rows, index=result.index)

    for column in TEXT_FEATURE_COLUMNS + CONTEXT_FEATURE_COLUMNS:
        result[column] = feature_df[column]

    return result


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    df = extract_text_features(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"텍스트/문맥 피처 추출 완료: {OUTPUT_PATH}")
    print("shape:", df.shape)
    print(df[
        [
            "post_id",
            "comment_id",
            "comment_text",
            "is_top_comment",
            "post_comment_overlap_count",
            "post_comment_jaccard",
            "post_comment_coverage",
            "post_comment_length_ratio",
        ]
    ].head())


if __name__ == "__main__":
    main()
