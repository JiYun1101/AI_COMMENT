"""수집된 사용자 피드백을 재학습용 CSV로 내보낸다.

``/recommendations/{id}/feedback``으로 쌓인 useful/not_useful 라벨은 지금까지
dashboard 집계에만 쓰이고 모델 학습에는 반영되지 않았다. 이 스크립트는 그
데이터를 학습 파이프라인이 읽을 수 있는 형태로 꺼내 준다.

실행:
    python -m scripts.export_feedback [출력경로]
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from src.config import BASE_DIR
from src.storage.analysis_store import list_feedback_examples

DEFAULT_OUTPUT = BASE_DIR / "data" / "processed" / "feedback_labels.csv"
COLUMNS = [
    "recommendation_id",
    "analysis_id",
    "post_text",
    "comment",
    "type",
    "category",
    "source_type",
    "predicted_score",
    "feedback",
    "label",
    "created_at",
]


def export(output_path: Path) -> int:
    rows = list_feedback_examples()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    count = export(output_path)
    positives = sum(1 for row in list_feedback_examples() if row["label"] == 1)
    print(f"피드백 {count}건 저장: {output_path}")
    if count:
        print(f"useful {positives} / not_useful {count - positives}")
    else:
        print("아직 피드백이 없습니다. UI에서 추천에 평가를 남기면 쌓입니다.")


if __name__ == "__main__":
    main()
