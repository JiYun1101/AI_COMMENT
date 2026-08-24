import joblib
import pandas as pd

from imblearn.under_sampling import RandomUnderSampler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit

from src.config import BASE_DIR
from src.features.feature_schema import FEATURE_COLUMNS


INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"
MODEL_PATH = BASE_DIR / "models" / "comment_ranker.joblib"
TARGET_COLUMN = "is_top_comment"
GROUP_COLUMN = "post_id"


def _group_split(X, y, groups):
    splitter = GroupShuffleSplit(
        n_splits=20,
        test_size=0.2,
        random_state=42,
    )

    for train_idx, test_idx in splitter.split(X, y, groups=groups):
        y_train = y.iloc[train_idx]
        y_test = y.iloc[test_idx]
        if y_train.nunique() == 2 and y_test.nunique() == 2:
            return train_idx, test_idx

    raise ValueError(
        "게시글 단위 Train/Test 분리 후 두 클래스가 모두 포함되는 split을 "
        "만들 수 없습니다. 데이터 분포를 확인하세요."
    )


def train_model():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    required_columns = FEATURE_COLUMNS + [TARGET_COLUMN, GROUP_COLUMN]
    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(f"학습 컬럼 누락: {missing_columns}")

    df = df.dropna(subset=[TARGET_COLUMN, GROUP_COLUMN]).copy()
    X = df[FEATURE_COLUMNS].fillna(0)
    y = df[TARGET_COLUMN].astype(int)
    groups = df[GROUP_COLUMN].astype(str)

    if y.nunique() < 2:
        raise ValueError(
            "타깃 클래스가 1개뿐입니다. 상위 댓글과 일반 댓글이 모두 필요합니다."
        )

    train_idx, test_idx = _group_split(X, y, groups)

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]
    train_groups = groups.iloc[train_idx]
    test_groups = groups.iloc[test_idx]

    overlap = set(train_groups) & set(test_groups)
    if overlap:
        raise AssertionError(f"Train/Test post_id 중복: {len(overlap)}")

    print("전체 데이터 shape:", df.shape)
    print("전체 클래스 분포")
    print(y.value_counts())
    print("Train 영상 수:", train_groups.nunique())
    print("Test 영상 수:", test_groups.nunique())
    print("Train/Test 영상 중복 수:", len(overlap))

    sampler = RandomUnderSampler(
        random_state=42,
        sampling_strategy="auto",
    )
    X_train_balanced, y_train_balanced = sampler.fit_resample(
        X_train,
        y_train,
    )

    print("언더샘플링 후 클래스 분포")
    print(y_train_balanced.value_counts())

    model = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=2,
    )
    model.fit(X_train_balanced, y_train_balanced)

    y_pred = model.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"F1 Score: {f1_score(y_test, y_pred, zero_division=0):.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    feature_importance = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)
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
    print(f"모델 저장 완료: {MODEL_PATH}")


if __name__ == "__main__":
    train_model()
