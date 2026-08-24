"""학습과 추론이 공유하는 모델 피처 스키마."""

from src.features.embedding_features import SIMILARITY_COLUMN
from src.features.text_features import (
    CONTEXT_FEATURE_COLUMNS,
    TEXT_FEATURE_COLUMNS,
)

FEATURE_COLUMNS = (
    TEXT_FEATURE_COLUMNS
    + CONTEXT_FEATURE_COLUMNS
    + [SIMILARITY_COLUMN]
)
