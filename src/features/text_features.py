import re
import pandas as pd

from src.config import BASE_DIR


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_likes_normalized.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"


CASUAL_WORDS = ["ㅋㅋ", "ㅎㅎ", "ㄹㅇ", "진짜", "개", "미쳤", "대박", "레전드"]
EMPATHY_WORDS = ["공감", "나도", "저도", "맞아요", "인정", "내 얘기", "그니까"]
INSIGHT_WORDS = ["결국", "핵심", "문제는", "이유는", "중요한 건", "포인트", "본질"]
CRITICISM_WORDS = ["별로", "문제", "아쉽", "싫", "망", "비판", "이상한"]


# 학습-추론 피처 드리프트 방지용 단일 텍스트 피처 컬럼 정의.
# extract_comment_features 가 이 목록과 정확히 일치하는 키를 반환한다.
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


def count_matches(text: str, words: list[str]) -> int:
    text = str(text)
    return sum(text.count(word) for word in words)


def extract_comment_features(comment: str) -> dict:
    """단일 댓글에서 텍스트 피처를 추출해 dict로 반환한다.

    학습 파이프라인(extract_text_features)과 추론 경로(predict.py)가 모두
    이 함수를 호출하므로 학습-추론 피처 드리프트가 발생하지 않는다.
    """
    text = str(comment or "")

    question_count = len(re.findall(r"\?", text))
    exclamation_count = len(re.findall(r"!", text))

    return {
        "comment_length": len(text),
        "word_count": len(text.split()),
        "sentence_count": max(1, len(re.findall(r"[.!?。！？]", text)) + 1),
        "question_count": question_count,
        "exclamation_count": exclamation_count,
        "laugh_count": text.count("ㅋㅋ") + text.count("ㅎㅎ"),
        "sad_count": text.count("ㅠㅠ") + text.count("ㅜㅜ"),
        "has_question": int(question_count > 0),
        "has_url": int(bool(re.search(r"http|www\.", text))),
        "has_number": int(bool(re.search(r"\d", text))),
        "casual_score": count_matches(text, CASUAL_WORDS),
        "empathy_score": count_matches(text, EMPATHY_WORDS),
        "insight_score": count_matches(text, INSIGHT_WORDS),
        "criticism_score": count_matches(text, CRITICISM_WORDS),
    }


def extract_text_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    text = df["comment_text"].fillna("").astype(str)
    feature_df = pd.DataFrame(
        text.apply(extract_comment_features).tolist(),
        index=df.index,
    )

    for column in TEXT_FEATURE_COLUMNS:
        df[column] = feature_df[column]

    return df


def main():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    df = extract_text_features(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"텍스트 피처 추출 완료: {OUTPUT_PATH}")
    print(df[[
        "comment_id",
        "comment_text",
        "comment_length",
        "word_count",
        "casual_score",
        "empathy_score",
        "insight_score",
        "criticism_score",
    ]])


if __name__ == "__main__":
    main()