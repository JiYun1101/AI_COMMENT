from __future__ import annotations

from functools import lru_cache

import joblib
import pandas as pd

from src.config import BASE_DIR
from src.features.embedding_features import (
    SIMILARITY_COLUMN,
    compute_post_comment_similarity,
)
from src.features.feature_schema import FEATURE_COLUMNS
from src.features.text_features import extract_feature_row as extract_lexical_features

MODEL_PATH = BASE_DIR / "models" / "comment_ranker.joblib"


class ModelNotReadyError(RuntimeError):
    pass


def extract_feature_row(post_text: str, comment: str) -> dict:
    features = extract_lexical_features(post_text, comment)
    features[SIMILARITY_COLUMN] = compute_post_comment_similarity(post_text, comment)
    return features


def model_readiness() -> dict:
    return {
        "ready": MODEL_PATH.exists(),
        "model_path": str(MODEL_PATH),
        "setup_command": "python -m src.model.train",
    }


@lru_cache(maxsize=1)
def load_ranker_model():
    if not MODEL_PATH.exists():
        raise ModelNotReadyError(
            "추천 모델이 준비되지 않았습니다. 데이터 준비 후 `python -m src.model.train`을 실행하세요."
        )

    loaded = joblib.load(MODEL_PATH)
    if not isinstance(loaded, dict):
        raise ModelNotReadyError(
            "기존 단일 객체 모델 형식은 현재 피처 스키마와 호환되지 않습니다. "
            "`python -m src.model.train`으로 모델을 다시 학습하세요."
        )

    model = loaded.get("model")
    if model is None:
        raise ModelNotReadyError("comment_ranker.joblib에 'model' 키가 없습니다. 모델을 다시 학습하세요.")

    saved_columns = loaded.get("feature_columns")
    if saved_columns != FEATURE_COLUMNS:
        raise ModelNotReadyError(
            "저장된 모델의 피처 스키마가 현재 코드와 다릅니다. "
            "`python -m src.model.train`으로 모델을 다시 학습하세요."
        )

    return model


def score_comments(post_text: str, comments: list[str]) -> list[dict]:
    if not comments:
        return []

    model = load_ranker_model()
    rows = [extract_feature_row(post_text, comment) for comment in comments]
    X = pd.DataFrame(rows)

    missing_columns = [column for column in FEATURE_COLUMNS if column not in X.columns]
    if missing_columns:
        raise ValueError(f"추론 피처 누락: {missing_columns}")

    X = X[FEATURE_COLUMNS].fillna(0)

    if hasattr(model, "predict_proba"):
        scores = model.predict_proba(X)[:, 1]
    else:
        scores = model.predict(X)

    results = [
        {"comment": comment, "score": round(float(score) * 100, 2)}
        for comment, score in zip(comments, scores)
    ]
    results.sort(key=lambda item: item["score"], reverse=True)
    return results


if __name__ == "__main__":
    sample_post = "AI 시대에 개발자는 어떻게 살아남아야 할까?"
    sample_comments = [
        "결국 문제를 정의하는 능력이 중요해질 것 같아요.",
        "좋은 글 감사합니다.",
        "이건 생각보다 현실적인 문제라 더 와닿네요 ㅋㅋ",
    ]

    for item in score_comments(sample_post, sample_comments):
        print(item)
