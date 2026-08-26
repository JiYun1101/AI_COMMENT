from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.config import BASE_DIR
from src.youtube.categories import save_category_names

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def fetch_categories(api_key: str, *, region_code: str = "KR") -> dict[str, str]:
    response = requests.get(
        f"{YOUTUBE_API_BASE}/videoCategories",
        params={"part": "snippet", "regionCode": region_code, "key": api_key},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    categories: dict[str, str] = {}
    for item in payload.get("items") or []:
        category_id = str(item.get("id") or "").strip()
        title = str((item.get("snippet") or {}).get("title") or "").strip()
        if category_id and title:
            categories[category_id] = title
    return categories


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync YouTube video categories into the runtime cache.")
    parser.add_argument("--region", default=os.getenv("YOUTUBE_CATEGORY_REGION", "KR"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env.local")
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise SystemExit("YOUTUBE_API_KEY가 필요합니다.")

    categories = fetch_categories(api_key, region_code=args.region)
    if not categories:
        raise SystemExit("YouTube category를 가져오지 못했습니다.")
    path = save_category_names(categories, args.output)
    print(f"YouTube category {len(categories)}개 저장: {path}")


if __name__ == "__main__":
    main()
