import pandas as pd

from src.features.feature_schema import FEATURE_COLUMNS
from src.features.text_features import (
    CONTEXT_FEATURE_COLUMNS,
    TEXT_FEATURE_COLUMNS,
    extract_feature_row,
    extract_text_features,
)


def test_schema_contains_text_context_and_similarity():
    assert FEATURE_COLUMNS == (
        TEXT_FEATURE_COLUMNS
        + CONTEXT_FEATURE_COLUMNS
        + ["post_comment_sim"]
    )


def test_batch_and_single_lexical_features_agree():
    rows = [
        {
            "post_text": "AI 시대 개발자의 문제 정의 능력",
            "comment_text": "결국 문제 정의가 핵심이네요 ㅋㅋ",
        },
        {
            "post_text": "퇴근 후 직장인 일상 브이로그",
            "comment_text": "퇴근 후 루틴 진짜 공감돼요!",
        },
        {
            "post_text": "",
            "comment_text": "",
        },
    ]
    source = pd.DataFrame(rows)
    batch = extract_text_features(source)

    for index, row in source.iterrows():
        single = extract_feature_row(
            row["post_text"],
            row["comment_text"],
        )
        for column in TEXT_FEATURE_COLUMNS + CONTEXT_FEATURE_COLUMNS:
            assert batch.loc[index, column] == single[column]


def test_missing_text_is_safe():
    features = extract_feature_row(None, None)
    assert features["comment_length"] == 0
    assert features["post_comment_overlap_count"] == 0
