import re
import pandas as pd

from src.config import BASE_DIR


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_likes_normalized.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"


CASUAL_WORDS = ["ㅋㅋ", "ㅎㅎ", "ㄹㅇ", "진짜", "개", "미쳤", "대박", "레전드"]
EMPATHY_WORDS = ["공감", "나도", "저도", "맞아요", "인정", "내 얘기", "그니까"]
INSIGHT_WORDS = ["결국", "핵심", "문제는", "이유는", "중요한 건", "포인트", "본질"]
CRITICISM_WORDS = ["별로", "문제", "아쉽", "싫", "망", "비판", "이상한"]


def count_matches(text: str, words: list[str]) -> int:
    text = str(text)
    return sum(text.count(word) for word in words)


def extract_text_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    text = df["comment_text"].fillna("").astype(str)

    df["comment_length"] = text.str.len()
    df["word_count"] = text.apply(lambda x: len(x.split()))
    df["sentence_count"] = text.apply(lambda x: max(1, len(re.findall(r"[.!?。！？]", x)) + 1))

    df["question_count"] = text.str.count(r"\?")
    df["exclamation_count"] = text.str.count(r"!")
    df["laugh_count"] = text.apply(lambda x: x.count("ㅋㅋ") + x.count("ㅎㅎ"))
    df["sad_count"] = text.apply(lambda x: x.count("ㅠㅠ") + x.count("ㅜㅜ"))

    df["has_question"] = (df["question_count"] > 0).astype(int)
    df["has_url"] = text.str.contains(r"http|www\.", regex=True).astype(int)
    df["has_number"] = text.str.contains(r"\d", regex=True).astype(int)

    df["casual_score"] = text.apply(lambda x: count_matches(x, CASUAL_WORDS))
    df["empathy_score"] = text.apply(lambda x: count_matches(x, EMPATHY_WORDS))
    df["insight_score"] = text.apply(lambda x: count_matches(x, INSIGHT_WORDS))
    df["criticism_score"] = text.apply(lambda x: count_matches(x, CRITICISM_WORDS))

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