from pathlib import Path

from src.recommender.historical_comments import build_historical_profile


def test_historical_profile_prefers_relevant_top_comments(tmp_path: Path):
    csv_path = tmp_path / "vlog_comments.csv"
    csv_path.write_text(
        "post_id,post_text,comment_id,comment_text,like_count,created_at,platform,category,reply_count,parent_id,video_view_count,is_top_comment\n"
        "v1,제주 여행 브이로그,c1,제주 맛집 정보 너무 유용해요!,120,2026-01-01T00:00:00Z,youtube,vlog,4,,10000,1\n"
        "v1,제주 여행 브이로그,c2,다음에는 어느 식당 가실지 궁금해요?,90,2026-01-01T00:00:00Z,youtube,vlog,3,,10000,1\n"
        "v2,회사 일상,c3,오늘도 잘 봤습니다 ㅋㅋ,2,2026-01-01T00:00:00Z,youtube,vlog,0,,10000,0\n",
        encoding="utf-8",
    )
    profile = build_historical_profile(
        "제주 여행 맛집 브이로그",
        topics=["travel", "food"],
        content_styles=["vlog"],
        dataset_paths=[csv_path],
    )
    assert profile["matched_count"] == 3
    assert profile["coverage"] == "matched_legacy_category"
    assert profile["reference_examples"][0] == "제주 맛집 정보 너무 유용해요!"
    assert profile["question_ratio"] > 0


def test_historical_profile_filters_unsafe_reference_text(tmp_path: Path):
    csv_path = tmp_path / "vlog_comments.csv"
    csv_path.write_text(
        "post_id,post_text,comment_id,comment_text,like_count,created_at,platform,category,reply_count,parent_id,video_view_count,is_top_comment\n"
        "v1,제주 여행 브이로그,c1,제주 맛집 정보 너무 유용해요!,50,2026-01-01T00:00:00Z,youtube,vlog,1,,10000,1\n"
        "v1,제주 여행 브이로그,c2,제주 여행 개새끼 진짜 싫다,999,2026-01-01T00:00:00Z,youtube,vlog,10,,10000,1\n",
        encoding="utf-8",
    )
    profile = build_historical_profile(
        "제주 여행 브이로그",
        topics=["travel"],
        content_styles=["vlog"],
        dataset_paths=[csv_path],
    )
    assert profile["matched_count"] == 1
    assert profile["reference_examples"] == ["제주 맛집 정보 너무 유용해요!"]


def test_historical_profile_tolerates_missing_dataset(tmp_path: Path):
    profile = build_historical_profile(
        "테스트",
        dataset_paths=[tmp_path / "missing.csv"],
    )
    assert profile["coverage"] == "none"
    assert profile["matched_count"] == 0
    assert profile["reference_examples"] == []


def test_reference_examples_do_not_mirror_excessive_laughter(tmp_path):
    import csv
    rows = [
        {
            "comment_text": f"즐거운 영상 보면서 웃었어요 ㅋㅋ {i}",
            "post_text": "즐거운 영상",
            "category": "vlog",
            "like_count": 80 - i,
            "reply_count": 0,
            "is_top_comment": 1,
        }
        for i in range(10)
    ] + [
        {
            "comment_text": f"촬영과 구도에 대한 차분한 관찰 {i}입니다",
            "post_text": "즐거운 영상",
            "category": "vlog",
            "like_count": 25 - i,
            "reply_count": 0,
            "is_top_comment": 1,
        }
        for i in range(8)
    ]
    path = tmp_path / "vlog_comments.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    profile = build_historical_profile(
        "즐거운 영상",
        topics=["lifestyle"],
        content_styles=["vlog"],
        dataset_paths=[path],
        reference_limit=6,
    )
    assert profile["matched_count"] == 18
    assert len(profile["reference_examples"]) == 6
    assert sum("ㅋㅋ" in text or "ㅎㅎ" in text for text in profile["reference_examples"]) <= 1
