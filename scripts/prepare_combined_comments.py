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
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]

    last_error = None

    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error

    raise last_error


def clean_parent_id(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.lower() in ["nan", "none", "null"]:
        return ""

    return text


def main():
    frames = []

    print("입력 파일 확인")

    for path in INPUT_FILES:
        if not path.exists():
            raise FileNotFoundError(f"입력 파일이 없습니다: {path}")

        print(f"- {path}")

        df = read_csv_with_fallback(path)

        missing_columns = [col for col in OUTPUT_COLUMNS if col not in df.columns]
        if missing_columns:
            raise ValueError(f"{path.name} 필수 컬럼 누락: {missing_columns}")

        frames.append(df)

    df = pd.concat(frames, ignore_index=True)

    print()
    print("원본 병합 shape:", df.shape)

    df["post_id"] = df["post_id"].astype(str)
    df["post_text"] = df["post_text"].astype(str).str.strip()
    df["comment_id"] = df["comment_id"].astype(str)
    df["comment_text"] = df["comment_text"].astype(str).str.strip()
    df["created_at"] = df["created_at"].astype(str)
    df["platform"] = df["platform"].astype(str)
    df["category"] = df["category"].astype(str)

    df["like_count"] = pd.to_numeric(df["like_count"], errors="coerce").fillna(0).astype(int)
    df["reply_count"] = pd.to_numeric(df["reply_count"], errors="coerce").fillna(0).astype(int)
    df["video_view_count"] = pd.to_numeric(df["video_view_count"], errors="coerce").fillna(0).astype(int)
    df["is_top_comment"] = pd.to_numeric(df["is_top_comment"], errors="coerce").fillna(0).astype(int)

    df["parent_id"] = df["parent_id"].apply(clean_parent_id)

    before_clean = len(df)

    df = df.dropna(subset=["post_id", "post_text", "comment_id", "comment_text"]).copy()
    df = df[df["comment_text"].str.len() > 0].copy()
    df = df.drop_duplicates(subset=["comment_id"]).copy()

    after_dedup = len(df)

    # 1차 추천 모델은 영상에 직접 다는 댓글 추천이므로 답글 제외
    before_top_level = len(df)
    df = df[df["parent_id"] == ""].copy()
    after_top_level = len(df)

    # 댓글이 너무 적은 영상 제외
    comment_count = df.groupby("post_id")["comment_id"].transform("count")
    df = df[comment_count >= 10].copy()

    # 좋아요가 전부 0인 영상 제외
    max_like_by_post = df.groupby("post_id")["like_count"].transform("max")
    df = df[max_like_by_post > 0].copy()

    df = df[OUTPUT_COLUMNS].copy()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print()
    print("통합 comments.csv 생성 완료")
    print(f"저장 경로: {OUTPUT_PATH}")
    print(f"정리 전 댓글 수: {before_clean}")
    print(f"중복 제거 후 댓글 수: {after_dedup}")
    print(f"답글 제외 전 댓글 수: {before_top_level}")
    print(f"답글 제외 후 댓글 수: {after_top_level}")
    print(f"최종 shape: {df.shape}")

    print()
    print("카테고리 분포")
    print(df["category"].value_counts())

    print()
    print("라벨 분포")
    print(df["is_top_comment"].value_counts())

    print()
    print("영상 수")
    print(df["post_id"].nunique())


if __name__ == "__main__":
    main()