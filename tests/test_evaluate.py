import numpy as np
import pandas as pd
import pytest

from src.features.feature_schema import FEATURE_COLUMNS
from src.model.evaluate import (
    evaluate_ranker,
    paired_bootstrap_ci,
    per_post_metrics,
)


class ScoreByColumn:
    """지정한 피처 값을 그대로 점수로 쓰는 모델 스텁."""

    def __init__(self, column: str, *, invert: bool = False) -> None:
        self.column = column
        self.invert = invert

    def predict_proba(self, X):
        scores = X[self.column].to_numpy(dtype=float)
        if self.invert:
            scores = -scores
        return np.column_stack([1 - scores, scores])


def _frame(posts: int = 3, comments: int = 10) -> pd.DataFrame:
    rows = []
    for post in range(posts):
        for index in range(comments):
            row = {column: 0.0 for column in FEATURE_COLUMNS}
            # comment_length가 클수록 상위 댓글이 되도록 구성한다.
            row["comment_length"] = float(index)
            row["post_id"] = f"p{post}"
            row["is_top_comment"] = 1 if index >= comments - 3 else 0
            rows.append(row)
    return pd.DataFrame(rows)


def test_perfect_ranker_reaches_maximum_ndcg():
    summary = evaluate_ranker(_frame(), ScoreByColumn("comment_length"), k=3)

    assert summary["model"]["ndcg"] == pytest.approx(1.0)
    assert summary["model"]["precision"] == pytest.approx(1.0)
    assert summary["model"]["mrr"] == pytest.approx(1.0)


def test_inverted_ranker_scores_worse_than_perfect_ranker():
    good = evaluate_ranker(_frame(), ScoreByColumn("comment_length"), k=3)
    bad = evaluate_ranker(_frame(), ScoreByColumn("comment_length", invert=True), k=3)

    assert bad["model"]["ndcg"] < good["model"]["ndcg"]
    assert bad["model"]["precision"] == 0.0


def test_posts_without_positives_or_enough_candidates_are_skipped():
    frame = _frame(posts=2, comments=10)
    frame.loc[frame["post_id"] == "p0", "is_top_comment"] = 0  # 정답 없음
    frame = pd.concat([frame, _frame(posts=1, comments=3).assign(post_id="p_short")])

    summary = evaluate_ranker(frame, ScoreByColumn("comment_length"), k=5)

    assert summary["_meta"]["evaluated_posts"] == 1.0


def test_length_baseline_is_reported_alongside_model():
    rows = per_post_metrics(_frame(), ScoreByColumn("comment_length"), k=3)

    assert set(rows) == {"model", "random", "length"}
    assert len(rows["model"]) == len(rows["length"]) == len(rows["random"]) == 3


def test_bootstrap_ci_brackets_a_zero_difference():
    rows = per_post_metrics(_frame(posts=8), ScoreByColumn("comment_length"), k=3)
    mean, low, high = paired_bootstrap_ci(rows["model"], rows["length"], iterations=200)

    # 동일한 순서를 만드는 두 ranker이므로 차이는 0이어야 한다.
    assert mean == pytest.approx(0.0)
    assert low <= 0 <= high


def test_bootstrap_ci_on_empty_input_is_zero():
    assert paired_bootstrap_ci([], [], iterations=10) == (0.0, 0.0, 0.0)
