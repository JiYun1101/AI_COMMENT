from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.config import BASE_DIR

CATEGORY_CACHE_PATH = BASE_DIR / "data" / "runtime" / "youtube_categories.json"

# Stable, commonly used YouTube video category ids. A synced runtime cache can
# override/extend these because availability and titles may vary by region.
BUILTIN_CATEGORY_NAMES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}


@lru_cache(maxsize=1)
def load_category_names(path: str | Path | None = None) -> dict[str, str]:
    names = dict(BUILTIN_CATEGORY_NAMES)
    cache_path = Path(path) if path is not None else CATEGORY_CACHE_PATH
    if not cache_path.exists():
        return names

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return names

    raw_categories = payload.get("categories", payload) if isinstance(payload, dict) else {}
    if isinstance(raw_categories, dict):
        for category_id, title in raw_categories.items():
            if category_id and isinstance(title, str) and title.strip():
                names[str(category_id)] = title.strip()
    return names


def resolve_category_name(category_id: str | None) -> str | None:
    if not category_id:
        return None
    return load_category_names().get(str(category_id))


def save_category_names(categories: dict[str, str], path: str | Path | None = None) -> Path:
    cache_path = Path(path) if path is not None else CATEGORY_CACHE_PATH
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"categories": dict(sorted(categories.items(), key=lambda item: int(item[0]) if item[0].isdigit() else 9999))}
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    load_category_names.cache_clear()
    return cache_path
