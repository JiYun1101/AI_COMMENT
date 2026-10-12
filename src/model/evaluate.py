"""Ranker를 실제 사용 방식대로 평가한다.

학습 스크립트가 출력하는 F1은 "이 댓글이 상위 20%인가"를 전체 데이터에 대해
맞히는 이진 분류 성능이다. 하지만 서비스에서 모델이 하는 일은 다르다. 한 영상에
대해 생성된 후보 몇십 개를 **그 영상 안에서** 재정렬해 상위 k개를 고르는 것이다.
그래서 여기서는 post 단위 랭킹 지표(NDCG@k, Precision@k, MRR)를 쓰고, 랜덤/길이
기준 baseline과 함께 출력한다. baseline을 유의미하게 넘지 못하면 랭킹 단계가
가치를 더하지 못하고 있다는 뜻이다.

실행:
    python -m src.model.evaluate
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.config import BASE_DIR
from src.features.feature_schema import FEATURE_COLUMNS

INPUT_PATH = BASE_DIR / "data" / "processed" / "comments_features.csv"
TARGET_COLUMN = "is_top_comment"
GROUP_COLUMN = "post_id"
DEFAULT_K = 5


def _dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(rank + 1) for rank, rel in enumerate(relevances, start=1))


def _ranking_metrics(labels: np.ndarray, scores: np.ndarray, k: int) -> dict[str, float]:
    """점수 내림차순으로 정렬했을 때의 NDCG@k / Precision@k / MRR."""
    order = np.argsort(-scores, kind="stable")
    ranked = labels[order]

    top_k = ranked[:k].tolist()
    ideal = sorted(labels.tolist(), reverse=True)[:k]

    ideal_dcg = _dcg(ideal)
    ndcg = (_dcg(top_k) / ideal_dcg) if ideal_dcg > 0 else 0.0

    hit_positions = np.flatnonzero(ranked == 1)
    mrr = 1.0 / (hit_positions[0] + 1) if hit_positions.size else 0.0

    return {
        "ndcg": ndcg,
        "precision": sum(top_k) / k,
        "mrr": mrr,
    }


def _model_scores(model, frame: pd.DataFrame) -> np.ndarray:
    X = frame[FEATURE_COLUMNS].fillna(0)
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    return np.asarray(model.predict(X), dtype=float)


def per_post_metrics(
    df: pd.DataFrame,
    model,
    *,
    k: int = DEFAULT_K,
    seed: int = 42,
) -> dict[str, list[dict[str, float]]]:
    """post별 랭킹 지표를 ranker(model/random/length)별로 모아 돌려준다.

    상위 댓글이 하나도 없거나 후보가 k개 이하인 post는 랭킹을 평가할 수 없으므로
    제외한다. 순서는 post 순서를 유지하므로 ranker 간 paired 비교가 가능하다.
    """
    rng = np.random.default_rng(seed)
    rows: dict[str, list[dict[str, float]]] = {"model": [], "random": [], "length": []}

    for _, group in df.groupby(GROUP_COLUMN, sort=False):
        labels = group[TARGET_COLUMN].to_numpy(dtype=int)
        if labels.sum() == 0 or len(group) <= k:
            continue

        rows["model"].append(_ranking_metrics(labels, _model_scores(model, group), k))
        rows["random"].append(_ranking_metrics(labels, rng.random(len(group)), k))
        rows["length"].append(
            _ranking_metrics(labels, group["comment_length"].to_numpy(dtype=float), k)
        )

    return rows


def evaluate_ranker(
    df: pd.DataFrame,
    model,
    *,
    k: int = DEFAULT_K,
    seed: int = 42,
) -> dict[str, dict[str, float]]:
    """모델과 baseline들의 post 단위 평균 랭킹 지표를 돌려준다."""
    rows = per_post_metrics(df, model, k=k, seed=seed)

    summary: dict[str, dict[str, float]] = {}
    for name, values in rows.items():
        if not values:
            summary[name] = {"ndcg": 0.0, "precision": 0.0, "mrr": 0.0}
            continue
        summary[name] = {
            metric: float(np.mean([value[metric] for value in values]))
            for metric in values[0]
        }
    summary["_meta"] = {"evaluated_posts": float(len(rows["model"])), "k": float(k)}
    return summary


def paired_bootstrap_ci(
    left: list[dict[str, float]],
    right: list[dict[str, float]],
    *,
    metric: str = "ndcg",
    iterations: int = 5_000,
    seed: int = 0,
) -> tuple[float, float, float]:
    """두 ranker의 post별 지표 차이(left - right)에 대한 평균과 95% 신뢰구간.

    held-out post 수가 적을 때 평균값만 보면 우열을 과신하기 쉽다. 구간이 0을
    포함하면 두 ranker의 차이는 이 데이터로 구분되지 않는다.
    """
    diffs = np.array(
        [item[metric] - other[metric] for item, other in zip(left, right)], dtype=float
    )
    if diffs.size == 0:
        return 0.0, 0.0, 0.0

    rng = np.random.default_rng(seed)
    samples = rng.choice(diffs, size=(iterations, diffs.size), replace=True).mean(axis=1)
    return float(diffs.mean()), float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def _format_table(summary: dict[str, dict[str, float]], k: int) -> str:
    header = f"{'ranker':<10}{f'NDCG@{k}':>10}{f'P@{k}':>10}{'MRR':>10}"
    lines = [header, "-" * len(header)]
    for name in ("model", "random", "length"):
        row = summary[name]
        lines.append(
            f"{name:<10}{row['ndcg']:>10.4f}{row['precision']:>10.4f}{row['mrr']:>10.4f}"
        )
    return "\n".join(lines)


def main() -> None:
    from src.model.predict import load_ranker_model
    from src.model.train import _group_split

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    df = df.dropna(subset=[TARGET_COLUMN, GROUP_COLUMN]).copy()
    df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)

    # 학습과 동일한 결정적 split을 재현해 held-out post만 평가한다.
    _, test_idx = _group_split(
        df[FEATURE_COLUMNS].fillna(0),
        df[TARGET_COLUMN],
        df[GROUP_COLUMN].astype(str),
    )
    test_df = df.iloc[test_idx]

    model = load_ranker_model()
    rows = per_post_metrics(test_df, model, k=DEFAULT_K)
    summary = evaluate_ranker(test_df, model, k=DEFAULT_K)
    evaluated = int(summary["_meta"]["evaluated_posts"])

    print(f"held-out post 수: {test_df[GROUP_COLUMN].nunique()} (평가 대상 {evaluated})")
    print(_format_table(summary, DEFAULT_K))
    print()

    for baseline in ("random", "length"):
        mean, low, high = paired_bootstrap_ci(rows["model"], rows[baseline])
        verdict = "구분 불가" if low <= 0 <= high else ("모델 우위" if mean > 0 else "baseline 우위")
        print(
            f"model - {baseline:<7} NDCG@{DEFAULT_K} 차이: "
            f"{mean:+.4f} (95% CI {low:+.4f} ~ {high:+.4f}) -> {verdict}"
        )


if __name__ == "__main__":
    main()
