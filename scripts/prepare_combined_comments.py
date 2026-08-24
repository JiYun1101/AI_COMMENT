from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"

INPUT_FILES = [
    RAW_DIR / "social_issues_comments.csv",
    RAW_DIR / "vlog_comments.csv",
]
OUTPUT_PATH = RAW_DIR / "comments.csv"

OUTPUT_COLUMNS = [
    "post_id",
    "post_text",
    "comment_id",
    "comment_text",
    "like_count",
    "created_at",
    "platform",
    "category",
    "reply_count",
    "parent_id",
    "video_view_count",
    "is_top_comment",
]


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error

    if last_error is not None:
        raise last_error
    raise ValueError(f"CSV를 읽을 수 없습니다: {path}")


def clean_parent_id(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def main():
    frames = []

    for path in INPUT_FILES:
        if not path.exists():
            raise FileNotFoundError(f"입력 파일이 없습니다: {path}")

        df = read_csv_with_fallback(path)
        missing_columns = [
            column for column in OUTPUT_COLUMNS if column not in df.columns
        ]
        if missing_columns:
            raise ValueError(
                f"{path.name} 필수 컬럼 누락: {missing_columns}"
            )
        frames.append(df[OUTPUT_COLUMNS].copy())

    df = pd.concat(frames, ignore_index=True)

    df = df.dropna(
        subset=["post_id", "post_text", "comment_id", "comment_text"]
    ).copy()

    for column in (
        "post_id",
        "post_text",
        "comment_id",
        "comment_text",
        "created_at",
        "platform",
        "category",
    ):
        df[column] = df[column].astype(str).str.strip()

    for column in (
        "like_count",
        "reply_count",
        "video_view_count",
        "is_top_comment",
    ):
        df[column] = (
            pd.to_numeric(df[column], errors="coerce")
            .fillna(0)
            .astype(int)
        )

    df["parent_id"] = df["parent_id"].apply(clean_parent_id)

    df = df[df["comment_text"].str.len() > 0].copy()
    df = df.drop_duplicates(subset=["comment_id"]).copy()
    df = df[df["parent_id"] == ""].copy()

    comment_count = df.groupby("post_id")["comment_id"].transform("count")
    df = df[comment_count >= 10].copy()

    max_like_by_post = df.groupby("post_id")["like_count"].transform("max")
    df = df[max_like_by_post > 0].copy()

    df = df[OUTPUT_COLUMNS].copy()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"통합 comments.csv 생성 완료: {OUTPUT_PATH}")
    print("최종 shape:", df.shape)
    print("카테고리 분포")
    print(df["category"].value_counts())
    print("라벨 분포")
    print(df["is_top_comment"].value_counts())
    print("영상 수:", df["post_id"].nunique())


if __name__ == "__main__":
    main()
