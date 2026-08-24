"""
YouTube 댓글 수집 스크립트 (사회이슈 / 브이로그 카테고리)

- '어떤 댓글이 반응이 좋은가'와 '어떤 댓글이 안전한가'를 학습시키기 위한
  고품질 댓글 데이터셋을 카테고리별로 수집한다.
- 조회수 규모(대박/니치)를 섞어 다양한 영상에서 수집하고,
  스팸/이모티콘 전용/비한국어 댓글을 걸러낸 뒤,
  영상 내 좋아요 상위 15%를 성공 댓글(is_top_comment=1)로 라벨링한다.

Usage:
    python scripts/collect_comments.py --category social_issues --target 5000
    python scripts/collect_comments.py --category vlog --target 5000
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env.local")

API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    sys.exit("YOUTUBE_API_KEY가 .env.local에 설정되어 있지 않습니다.")

BASE = "https://www.googleapis.com/youtube/v3"

QUERIES = {
    "social_issues": [
        "시사 이슈 뉴스",
        "사회 이슈 토론",
        "정치 논쟁",
        "사회 문제 다큐",
    ],
    "vlog": [
        "일상 브이로그",
        "직장인 브이로그",
        "자취 브이로그",
        "여행 브이로그",
    ],
}

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U0001F000-\U0001F0FF"
    "\U00002600-\U000026FF"
    "\U0001F1E6-\U0001F1FF"
    "⬀-⯿"
    "⌀-⏿"
    "]+",
    flags=re.UNICODE,
)

SPAM_PATTERNS = [
    r"구독\s*(부탁|눌러|해주|좀)",
    r"좋아요\s*(부탁|눌러|좀)",
    r"https?://",
    r"카톡\s*(아이디|추가)",
    r"오픈\s*채팅",
    r"텔레그램",
    r"라인\s*아이디",
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    r"\d{2,3}[-.]\d{3,4}[-.]\d{4}",
    r"(맞팔|서이추|품앗이)",
]
SPAM_RE = re.compile("|".join(SPAM_PATTERNS))

HANGUL_RE = re.compile(r"[가-힣]")


def is_noise(text: str) -> bool:
    if not text:
        return True
    stripped = EMOJI_PATTERN.sub("", text).strip()
    if len(stripped) < 2:
        return True
    if SPAM_RE.search(text):
        return True
    hangul_count = len(HANGUL_RE.findall(text))
    if hangul_count < 2 or hangul_count / max(len(stripped), 1) < 0.3:
        return True
    return False


def api_get(path, params, session, units_tracker):
    params = {**params, "key": API_KEY}
    for attempt in range(3):
        resp = session.get(f"{BASE}/{path}", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (403, 429):
            print(f"  [WARN] {path} -> {resp.status_code}: {resp.text[:200]}")
            return None
        time.sleep(1.5 * (attempt + 1))
    return None


def search_videos(query, order, session, units_tracker, max_pages=1):
    video_ids = []
    page_token = None
    for _ in range(max_pages):
        params = {
            "part": "id",
            "q": query,
            "type": "video",
            "order": order,
            "maxResults": 50,
            "regionCode": "KR",
            "relevanceLanguage": "ko",
        }
        if page_token:
            params["pageToken"] = page_token
        data = api_get("search", params, session, units_tracker)
        units_tracker["units"] += 100
        if not data:
            break
        video_ids.extend(item["id"]["videoId"] for item in data.get("items", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return video_ids


def fetch_video_meta(video_ids, session, units_tracker):
    meta = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        params = {"part": "snippet,statistics", "id": ",".join(chunk)}
        data = api_get("videos", params, session, units_tracker)
        units_tracker["units"] += 1
        if not data:
            continue
        for item in data.get("items", []):
            meta[item["id"]] = {
                "title": item["snippet"]["title"],
                "view_count": int(item["statistics"].get("viewCount", 0)),
            }
    return meta


def fetch_comment_threads(video_id, session, units_tracker, max_pages=3):
    threads = []
    page_token = None
    for _ in range(max_pages):
        params = {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": 100,
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        data = api_get("commentThreads", params, session, units_tracker)
        units_tracker["units"] += 1
        if not data:
            break
        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            threads.append({
                "comment_id": item["snippet"]["topLevelComment"]["id"],
                "text": top["textDisplay"],
                "like_count": top["likeCount"],
                "reply_count": item["snippet"]["totalReplyCount"],
                "published_at": top["publishedAt"],
                "parent_id": None,
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return threads


def fetch_replies(comment_id, session, units_tracker, max_results=100):
    replies = []
    params = {
        "part": "snippet",
        "parentId": comment_id,
        "maxResults": max_results,
        "textFormat": "plainText",
    }
    data = api_get("comments", params, session, units_tracker)
    units_tracker["units"] += 1
    if not data:
        return replies
    for item in data.get("items", []):
        s = item["snippet"]
        replies.append({
            "comment_id": item["id"],
            "text": s["textDisplay"],
            "like_count": s["likeCount"],
            "reply_count": 0,
            "published_at": s["publishedAt"],
            "parent_id": comment_id,
        })
    return replies


def label_top_comments(rows, top_pct=0.15, min_comments=10):
    from collections import defaultdict
    by_video = defaultdict(list)
    for r in rows:
        by_video[r["video_id"]].append(r)
    for video_rows in by_video.values():
        if len(video_rows) < min_comments:
            for r in video_rows:
                r["is_top_comment"] = 0
            continue
        sorted_rows = sorted(video_rows, key=lambda r: r["like_count"], reverse=True)
        cutoff = max(1, int(len(sorted_rows) * top_pct))
        top_ids = {id(r) for r in sorted_rows[:cutoff]}
        for r in video_rows:
            r["is_top_comment"] = 1 if id(r) in top_ids else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True, choices=list(QUERIES.keys()))
    parser.add_argument("--target", type=int, default=5000)
    parser.add_argument("--max-units", type=int, default=4500)
    parser.add_argument("--reply-budget", type=int, default=250)
    args = parser.parse_args()

    session = requests.Session()
    units_tracker = {"units": 0}

    print(f"[1/4] '{args.category}' 카테고리 영상 검색 중...")
    video_ids = set()
    for query in QUERIES[args.category]:
        for order in ("viewCount", "relevance"):
            if units_tracker["units"] >= args.max_units:
                break
            ids = search_videos(query, order, session, units_tracker, max_pages=1)
            video_ids.update(ids)
            print(f"  query='{query}' order={order} -> +{len(ids)} videos "
                  f"(누적 units={units_tracker['units']})")

    video_ids = list(video_ids)
    print(f"  총 후보 영상 수: {len(video_ids)}")

    print("[2/4] 영상 메타데이터(조회수) 수집 중...")
    meta = fetch_video_meta(video_ids, session, units_tracker)

    print("[3/4] 댓글 수집 중 (target={})...".format(args.target))
    rows = []
    seen_ids = set()
    reply_calls_used = 0
    for vid in video_ids:
        if len(rows) >= args.target * 1.3 or units_tracker["units"] >= args.max_units:
            break
        vmeta = meta.get(vid)
        if not vmeta:
            continue
        threads = fetch_comment_threads(vid, session, units_tracker, max_pages=3)
        for t in threads:
            if t["comment_id"] in seen_ids:
                continue
            if is_noise(t["text"]):
                continue
            seen_ids.add(t["comment_id"])
            t["video_id"] = vid
            t["video_title"] = vmeta["title"]
            t["video_view_count"] = vmeta["view_count"]
            t["category"] = args.category
            rows.append(t)

            if (t["reply_count"] and 1 <= t["reply_count"] <= 5
                    and reply_calls_used < args.reply_budget):
                reply_calls_used += 1
                for rep in fetch_replies(t["comment_id"], session, units_tracker):
                    if rep["comment_id"] in seen_ids or is_noise(rep["text"]):
                        continue
                    seen_ids.add(rep["comment_id"])
                    rep["video_id"] = vid
                    rep["video_title"] = vmeta["title"]
                    rep["video_view_count"] = vmeta["view_count"]
                    rep["category"] = args.category
                    rows.append(rep)

        print(f"  video={vid} 누적 댓글={len(rows)} units={units_tracker['units']}")

    print(f"[4/4] 라벨링 및 저장 중... (수집된 댓글 수: {len(rows)})")
    label_top_comments(rows)

    out_dir = ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.category}_comments.csv"
    fieldnames = [
        "post_id", "post_text", "comment_id", "comment_text", "like_count",
        "created_at", "platform", "category", "reply_count", "parent_id",
        "video_view_count", "is_top_comment",
    ]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "post_id": r["video_id"],
                "post_text": r["video_title"],
                "comment_id": r["comment_id"],
                "comment_text": r["text"],
                "like_count": r["like_count"],
                "created_at": r["published_at"],
                "platform": "youtube",
                "category": r["category"],
                "reply_count": r["reply_count"],
                "parent_id": r["parent_id"],
                "video_view_count": r["video_view_count"],
                "is_top_comment": r["is_top_comment"],
            })

    print(f"완료: {out_path} ({len(rows)}건, API units 사용량={units_tracker['units']})")


if __name__ == "__main__":
    main()
