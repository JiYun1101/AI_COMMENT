import math
import pandas as pd

from src.config import BASE_DIR


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_processed.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "comments_likes_normalized.csv"


def normalize_likes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["log_like_count"] = df["like_count"].apply(lambda x: math.log(max(x, 0) + 1))

    df["like_rank_pct"] = df.groupby("post_id")["like_count"].rank(
        method="average",
        pct=True
    )

    group_mean = df.groupby("post_id")["like_count"].transform("mean")
    group_std = df.groupby("post_id")["like_count"].transform("std").fillna(0)

    df["like_zscore"] = (df["like_count"] - group_mean) / group_std.replace(0, 1)

    df["is_top_comment"] = (df["like_rank_pct"] >= 0.8).astype(int)
    df["is_bottom_comment"] = (df["like_rank_pct"] <= 0.5).astype(int)

    return df


def main():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    df = normalize_likes(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"좋아요 정규화 완료: {OUTPUT_PATH}")
    print(df[[
        "post_id",
        "comment_id",
        "comment_text",
        "like_count",
        "like_rank_pct",
        "like_zscore",
        "is_top_comment",
        "is_bottom_comment",
    ]])


if __name__ == "__main__":
    main()