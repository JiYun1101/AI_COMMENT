import joblib
import pandas as pd

from imblearn.under_sampling import RandomUnderSampler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit

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
    "post_comment_overlap_count",
    "post_comment_jaccard",
    "post_comment_coverage",
    "post_comment_length_ratio",
]

TARGET_COLUMN = "is_top_comment"
GROUP_COLUMN = "post_id"


def train_model():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    missing_features = [
        column
        for column in FEATURE_COLUMNS
        if column not in df.columns
    ]

    if missing_features:
        raise ValueError(f"피처 컬럼 누락: {missing_features}")

    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"타깃 컬럼이 없습니다: {TARGET_COLUMN}")

    if GROUP_COLUMN not in df.columns:
        raise ValueError(f"그룹 컬럼이 없습니다: {GROUP_COLUMN}")

    df = df.dropna(subset=[TARGET_COLUMN, GROUP_COLUMN]).copy()

    X = df[FEATURE_COLUMNS].fillna(0)
    y = df[TARGET_COLUMN].astype(int)
    groups = df[GROUP_COLUMN].astype(str)

    if y.nunique() < 2:
        raise ValueError("타깃 클래스가 1개뿐입니다. 상위 댓글과 일반 댓글이 모두 필요합니다.")

    print("전체 데이터 shape")
    print(df.shape)
    print()

    print("전체 클래스 분포")
    print(y.value_counts())
    print()

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.2,
        random_state=42,
    )

    train_idx, test_idx = next(splitter.split(X, y, groups=groups))

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    train_groups = groups.iloc[train_idx]
    test_groups = groups.iloc[test_idx]

    print("Train 영상 수:", train_groups.nunique())
    print("Test 영상 수:", test_groups.nunique())
    print("Train/Test 영상 중복 수:", len(set(train_groups) & set(test_groups)))
    print()

    print("원본 학습 데이터 클래스 분포")
    print(y_train.value_counts())
    print()

    sampler = RandomUnderSampler(
        random_state=42,
        sampling_strategy="auto",
    )

    X_train_balanced, y_train_balanced = sampler.fit_resample(
        X_train,
        y_train,
    )

    print("언더샘플링 후 학습 데이터 클래스 분포")
    print(y_train_balanced.value_counts())
    print()

    model = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=2,
    )

    model.fit(X_train_balanced, y_train_balanced)

    y_pred = model.predict(X_test)

    print("모델 학습 완료")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"F1 Score: {f1_score(y_test, y_pred, zero_division=0):.4f}")
    print()
    print(classification_report(y_test, y_pred, zero_division=0))

    feature_importance = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    print()
    print("Feature Importance")
    print(feature_importance)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "group_column": GROUP_COLUMN,
            "sampler": sampler,
        },
        MODEL_PATH,
    )

    print()
    print(f"모델 저장 완료: {MODEL_PATH}")


if __name__ == "__main__":
    train_model()