import re
import pandas as pd

from src.config import RAW_DATA_PATH, PROCESSED_DATA_PATH, REQUIRED_COLUMNS


def clean_text(text: str) -> str:
    text = str(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def validate_columns(df: pd.DataFrame) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing}")


def preprocess():
    try:
        df = pd.read_csv(RAW_DATA_PATH, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(RAW_DATA_PATH, encoding="cp949")

    validate_columns(df)

    df = df.dropna(subset=["post_id", "comment_id", "comment_text"])
    df["post_text"] = df["post_text"].fillna("")
    df["like_count"] = df["like_count"].fillna(0).astype(int)

    df["comment_text"] = df["comment_text"].apply(clean_text)
    df["post_text"] = df["post_text"].apply(clean_text)

    df = df.drop_duplicates(subset=["post_id", "comment_id"])
    df = df.drop_duplicates(subset=["post_id", "comment_text"])

    df["comment_count_in_post"] = df.groupby("post_id")["comment_id"].transform("count")

    PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_DATA_PATH, index=False, encoding="utf-8-sig")

    print(f"전처리 완료: {PROCESSED_DATA_PATH}")
    print(df.head())


if __name__ == "__main__":
    preprocess()