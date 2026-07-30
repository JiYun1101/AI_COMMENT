import joblib
import pandas as pd
from pathlib import Path

from src.features.embedding_features import (
    SIMILARITY_COLUMN,
    compute_post_comment_similarity,
)
from src.features.feature_schema import FEATURE_COLUMNS
from src.features.text_features import extract_comment_features

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "models" / "comment_ranker.joblib"


def extract_feature_row(post_text: str, comment: str) -> dict:
    """단일 (게시글, 댓글) 쌍에 대한 전체 피처 행을 반환한다.

    텍스트 피처는 학습 파이프라인과 동일한 ``extract_comment_features`` 를,
    임베딩 유사도는 ``compute_post_comment_similarity`` 를 사용하므로
    학습-추론 피처 드리프트가 발생하지 않는다.
    """
    features = extract_comment_features(comment)
    features[SIMILARITY_COLUMN] = compute_post_comment_similarity(post_text, comment)
    return features


def load_ranker_model():
    loaded = joblib.load(MODEL_PATH)

    if isinstance(loaded, dict):
        model = loaded.get("model")

        if model is None:
            raise ValueError(
                "comment_ranker.joblib이 dict로 저장되어 있지만 'model' 키가 없습니다."
            )

        feature_columns = loaded.get("feature_columns", FEATURE_COLUMNS)
        return model, feature_columns

    return loaded, FEATURE_COLUMNS


def score_comments(post_text: str, comments: list[str]) -> list[dict]:
    model, feature_columns = load_ranker_model()

    rows = [extract_feature_row(post_text, comment) for comment in comments]

    X = pd.DataFrame(rows)

    for column in feature_columns:
        if column not in X.columns:
            X[column] = 0

    X = X[feature_columns]

    if hasattr(model, "predict_proba"):
        scores = model.predict_proba(X)[:, 1]
    else:
        scores = model.predict(X)

    results = []

    for comment, score in zip(comments, scores):
        results.append(
            {
                "comment": comment,
                "score": round(float(score) * 100, 2),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)

    return results


if __name__ == "__main__":
    sample_post = "AI 시대에 개발자는 어떻게 살아남아야 할까?"
    sample_comments = [
        "결국 문제를 정의하는 능력이 중요해질 것 같아요.",
        "좋은 글 감사합니다.",
        "이건 생각보다 현실적인 문제라 더 와닿네요 ㅋㅋ",
    ]

    result = score_comments(
        post_text=sample_post,
        comments=sample_comments,
    )

    print("댓글 후보 점수화 결과")

    for item in result:
        print(item)