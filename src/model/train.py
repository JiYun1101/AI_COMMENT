import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report

from imblearn.under_sampling import RandomUnderSampler

from src.config import BASE_DIR


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"
MODEL_PATH = BASE_DIR / "models" / "comment_ranker.joblib"


FEATURE_COLUMNS = [
    "comment_length",
    "word_count",
    "sentence_count",
    "question_count",
    "exclamation_count",
    "laugh_count",
    "sad_count",
    "has_question",
    "has_url",
    "has_number",
    "casual_score",
    "empathy_score",
    "insight_score",
    "criticism_score",
]


TARGET_COLUMN = "is_top_comment"


def train_model():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    X = df[FEATURE_COLUMNS].fillna(0)
    y = df[TARGET_COLUMN]

    if y.nunique() < 2:
        raise ValueError("타깃 클래스가 1개뿐입니다. 상위 댓글과 일반 댓글이 모두 필요합니다.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.4,
        random_state=42,
        stratify=y if len(df) >= 5 else None,
    )

    print("원본 학습 데이터 클래스 분포")
    print(y_train.value_counts())
    print()

    sampler = RandomUnderSampler(
        random_state=42,
        sampling_strategy="auto",
    )

    X_train_balanced, y_train_balanced = sampler.fit_resample(X_train, y_train)

    print("언더샘플링 후 학습 데이터 클래스 분포")
    print(y_train_balanced.value_counts())
    print()

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train_balanced, y_train_balanced)

    y_pred = model.predict(X_test)

    print("모델 학습 완료")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"F1 Score: {f1_score(y_test, y_pred, zero_division=0):.4f}")
    print()
    print(classification_report(y_test, y_pred, zero_division=0))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "sampler": sampler,
        },
        MODEL_PATH,
    )

    print(f"모델 저장 완료: {MODEL_PATH}")


if __name__ == "__main__":
    train_model()