import math

import pandas as pd

from src.config import BASE_DIR


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_processed.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "comments_likes_normalized.csv"


def normalize_likes(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    result["log_like_count"] = result["like_count"].apply(
        lambda x: math.log(max(x, 0) + 1)
    )
    result["like_rank_pct"] = result.groupby("post_id")["like_count"].rank(
        method="average",
        pct=True,
    )

    group_mean = result.groupby("post_id")["like_count"].transform("mean")
    group_std = result.groupby("post_id")["like_count"].transform("std").fillna(0)
    result["like_zscore"] = (
        (result["like_count"] - group_mean)
        / group_std.replace(0, 1)
    )

    if "is_top_comment" not in result.columns:
        result["is_top_comment"] = (
            result["like_rank_pct"] >= 0.8
        ).astype(int)
    else:
        result["is_top_comment"] = (
            pd.to_numeric(result["is_top_comment"], errors="coerce")
            .fillna(0)
            .astype(int)
        )

    result["is_bottom_comment"] = (
        result["like_rank_pct"] <= 0.5
    ).astype(int)

    return result


def main():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    df = normalize_likes(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"좋아요 정규화 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
