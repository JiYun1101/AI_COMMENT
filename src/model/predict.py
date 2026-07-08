import joblib
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "models" / "comment_ranker.joblib"

FEATURE_COLUMNS = [
    "comment_length",
    "word_count",
    "question_count",
    "exclamation_count",
    "laugh_count",
    "has_question",
    "has_laugh",
    "empathy_score",
    "insight_score",
    "negative_score",
]


def extract_simple_features(comment: str) -> dict:
    return {
        "comment_length": len(comment),
        "word_count": len(comment.split()),
        "question_count": comment.count("?"),
        "exclamation_count": comment.count("!"),
        "laugh_count": comment.count("ㅋㅋ") + comment.count("ㅎㅎ"),
        "has_question": int("?" in comment),
        "has_laugh": int(("ㅋㅋ" in comment) or ("ㅎㅎ" in comment)),
        "empathy_score": int(
            any(word in comment for word in ["공감", "와닿", "맞아요", "진짜"])
        ),
        "insight_score": int(
            any(word in comment for word in ["핵심", "결국", "중요", "관점", "설계", "정의"])
        ),
        "negative_score": int(
            any(word in comment for word in ["별로", "최악", "싫다", "꺼져", "멍청"])
        ),
    }


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

    rows = []

    for comment in comments:
        features = extract_simple_features(comment)
        rows.append(features)

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