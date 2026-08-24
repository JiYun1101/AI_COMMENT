import pandas as pd

from src.features.like_normalizer import normalize_likes


def test_existing_top_comment_labels_are_preserved():
    df = pd.DataFrame(
        {
            "post_id": ["a", "a", "a"],
            "like_count": [100, 10, 1],
            "is_top_comment": [0, 1, 0],
        }
    )

    result = normalize_likes(df)
    assert result["is_top_comment"].tolist() == [0, 1, 0]


def test_label_is_created_for_legacy_data_without_label():
    df = pd.DataFrame(
        {
            "post_id": ["a", "a", "a", "a", "a"],
            "like_count": [1, 2, 3, 4, 5],
        }
    )

    result = normalize_likes(df)
    assert "is_top_comment" in result.columns
    assert result["is_top_comment"].sum() >= 1
