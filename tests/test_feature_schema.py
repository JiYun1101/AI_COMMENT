"""학습-추론 피처 스키마 일관성 회귀 테스트.

과거 predict.py 가 train.py 와 다른 피처 집합(has_laugh, negative_score 등)을
만들어, 학습 피처 15개 중 6개가 추론 시 항상 0으로 채워지는 조용한 버그가
있었다. 이 테스트는 두 경로가 동일한 스키마를 공유하는지 고정한다.
"""

import pandas as pd

from src.features.feature_schema import FEATURE_COLUMNS
from src.features.text_features import (
    TEXT_FEATURE_COLUMNS,
    extract_comment_features,
    extract_text_features,
)


def test_schema_is_text_features_plus_similarity():
    assert FEATURE_COLUMNS == TEXT_FEATURE_COLUMNS + ["post_comment_sim"]


def test_single_comment_extractor_matches_schema():
    features = extract_comment_features("결국 문제 정의가 핵심이네요 ㅋㅋ")
    assert list(features.keys()) == TEXT_FEATURE_COLUMNS


def test_batch_and_single_text_extraction_agree():
    """학습(DataFrame 일괄)과 추론(단일 댓글) 텍스트 피처가 동일해야 한다."""
    comments = [
        "결국 문제를 정의하는 능력이 중요해질 것 같아요.",
        "좋은 글 감사합니다",
        "이거 진짜 공감돼요 ㅋㅋㅋ 저도 그랬어요!!",
        "https://example.com 참고하세요 2024년 자료",
        "",
    ]
    df = extract_text_features(pd.DataFrame({"comment_text": comments}))

    for i, comment in enumerate(comments):
        single = extract_comment_features(comment)
        for column in TEXT_FEATURE_COLUMNS:
            assert df.loc[i, column] == single[column], (
                f"'{comment}' 의 {column} 이 배치/단일 경로에서 불일치"
            )


def test_extract_comment_features_handles_missing_text():
    """NaN/None 댓글도 예외 없이 0 피처를 반환해야 한다."""
    features = extract_comment_features(None)
    assert features["comment_length"] == 0
    assert features["word_count"] == 0
    assert list(features.keys()) == TEXT_FEATURE_COLUMNS
