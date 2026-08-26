from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.recommender.historical_comments import build_historical_profile

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9+#.-]{2,}")
_STOPWORDS = {
    "그리고", "하지만", "그래서", "이번", "영상", "대한", "대해", "관련", "내용", "정리", "이야기",
    "합니다", "했습니다", "있는", "없는", "하는", "되는", "제목", "채널", "설명", "자막", "스크립트",
    "the", "and", "for", "with", "this", "that", "from", "about", "video", "youtube", "into", "your",
    "you", "are", "was", "were", "have", "has", "had", "how", "why", "what", "when", "where", "who",
    "which", "will", "can", "could", "would", "should", "not", "but", "all", "new", "out", "our", "their",
    "they", "them", "its", "it's", "to", "of", "in", "on", "at", "by", "is", "it", "as", "an", "a",
    "be", "or", "if", "we", "my",
}

TOPIC_RULES: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "인공지능", "llm", "gpt", "머신러닝", "딥러닝"),
    "software": ("개발자", "프로그래밍", "코딩", "software", "frontend", "backend", "react", "python", "javascript"),
    "hardware": ("cpu", "gpu", "반도체", "hardware", "컴퓨터", "노트북"),
    "mobile": ("스마트폰", "갤럭시", "아이폰", "iphone", "android", "fold", "모바일"),
    "science": ("과학", "science", "연구", "실험", "우주", "물리", "화학", "생물"),
    "technology": ("기술", "technology", "tech", "로봇", "robot", "산업"),
    "career": ("커리어", "취업", "이직", "면접", "직장", "career", "job"),
    "education": ("교육", "공부", "수능", "학교", "대학", "강의", "course"),
    "finance": ("주식", "투자", "금리", "재테크", "finance", "stock", "crypto", "코인"),
    "economy": ("경제", "물가", "부동산", "economy", "inflation"),
    "politics": ("정치", "대통령", "정부", "국회", "선거", "politics", "election"),
    "law": ("법률", "규제", "정책", "제도", "law", "regulation"),
    "beauty": ("메이크업", "화장품", "스킨케어", "뷰티", "beauty", "makeup", "cosmetic"),
    "fashion": ("패션", "코디", "fashion", "outfit"),
    "food": ("맛집", "먹방", "요리", "레시피", "음식", "food", "recipe", "restaurant"),
    "travel": ("여행", "관광", "호텔", "제주", "부산", "travel", "trip"),
    "fitness": ("운동", "헬스", "러닝", "클라이밍", "fitness", "workout", "gym"),
    "health": ("건강", "의학", "병원", "영양", "health", "medical", "diet"),
    "relationships": ("연애", "데이트", "결혼", "relationship", "dating"),
    "music": ("음악", "노래", "가수", "뮤직비디오", "music", "song", "album"),
    "film": ("영화", "드라마", "배우", "film", "movie", "cinema", "series"),
    "animation": ("애니", "애니메이션", "animation", "anime"),
    "gaming": ("게임", "게이밍", "game", "gaming", "공략"),
    "sports": ("스포츠", "축구", "야구", "농구", "테니스", "sports", "football", "baseball", "basketball"),
    "animals": ("고양이", "강아지", "반려동물", "동물", "cat", "dog", "pet", "animal"),
    "autos": ("자동차", "차량", "전기차", "car", "vehicle", "tesla", "현대차"),
    "lifestyle": ("일상", "루틴", "자취", "브이로그", "daily", "routine", "vlog"),
    "shopping": ("쇼핑", "구매", "haul", "shopping", "세일", "추천템"),
    "news": ("뉴스", "속보", "브리핑", "news", "breaking"),
}

STYLE_RULES: dict[str, tuple[str, ...]] = {
    "educational": ("강의", "설명", "정리", "교육", "lecture", "explained", "learn"),
    "tutorial": ("방법", "하는 법", "가이드", "튜토리얼", "tutorial", "how to", "guide"),
    "review": ("리뷰", "후기", "사용기", "review", "hands-on"),
    "comparison": ("비교", " vs ", "comparison", "versus"),
    "discussion": ("토론", "논의", "discussion", "debate"),
    "interview": ("인터뷰", "대담", "interview", "q&a"),
    "commentary": ("분석", "해설", "의견", "commentary", "analysis"),
    "news": ("뉴스", "속보", "브리핑", "news", "breaking"),
    "reaction": ("리액션", "reaction", "reacts"),
    "vlog": ("브이로그", "vlog", "일상", "day in my life", "루틴"),
    "challenge": ("챌린지", "challenge", "도전"),
    "entertainment": ("예능", "웃긴", "재미", "entertainment", "funny"),
    "performance": ("공연", "무대", "라이브 클립", "performance", "concert", "stage"),
    "highlights": ("하이라이트", "highlight", "best moments"),
    "unboxing": ("언박싱", "unboxing", "개봉"),
}

AGE_RULES: dict[str, tuple[str, ...]] = {
    "children": ("어린이", "키즈", "유아", "초등", "kids", "children", "toddler"),
    "teens": ("중학생", "고등학생", "수능", "10대", "teen", "high school"),
    "young_adult": ("대학생", "취준", "신입", "자취", "20대", "college", "entry level"),
    "adult": ("직장인", "육아", "결혼", "부모", "30대", "40대", "adult"),
    "mature": ("중년", "은퇴", "노후", "50대", "60대", "senior", "retirement"),
}

FEMALE_TERMS = ("여성", "여자", "여대생", "여친", "여성용", "women", "woman", "girl")
MALE_TERMS = ("남성", "남자", "남친", "남성용", "men", "man", "boy")


def _extract_keywords(text: str, limit: int = 12) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text or ""):
        token = raw.strip(".-").lower()
        if len(token) >= 2 and token not in _STOPWORDS and not token.isdigit():
            tokens.append(token)
    counts = Counter(tokens)
    first_position = {token: tokens.index(token) for token in counts}
    ranked = sorted(counts, key=lambda token: (-counts[token], first_position[token]))
    return ranked[:limit]


def _match_labels(text: str, rules: dict[str, tuple[str, ...]], limit: int) -> list[str]:
    lowered = text.lower()
    scored = []
    for label, keywords in rules.items():
        score = sum(1 for keyword in keywords if keyword.lower() in lowered)
        if score:
            scored.append((score, label))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [label for _, label in scored[:limit]]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _freshness(age_hours: float | None) -> str:
    if age_hours is None:
        return "unknown"
    if age_hours < 24:
        return "breaking"
    if age_hours < 72:
        return "fresh"
    if age_hours < 168:
        return "recent"
    if age_hours < 720:
        return "current"
    if age_hours < 24 * 30 * 6:
        return "established"
    if age_hours < 24 * 365 * 2:
        return "old"
    return "evergreen"


def _season(month: int | None) -> str | None:
    if month in {3, 4, 5}:
        return "spring"
    if month in {6, 7, 8}:
        return "summer"
    if month in {9, 10, 11}:
        return "autumn"
    if month:
        return "winter"
    return None


def _format_kind(duration: int | None, is_short: bool | None) -> str:
    if is_short:
        return "short"
    if duration is None:
        return "unknown"
    if duration <= 180:
        return "short_like"
    return "long_form" if duration >= 1200 else "standard"


def _broadcast_kind(value: str | None, details: dict[str, Any] | None) -> str:
    normalized = (value or "none").lower()
    if normalized == "live":
        return "live"
    if normalized == "upcoming":
        return "upcoming"
    if (details or {}).get("actualStartTime") or (details or {}).get("actualEndTime"):
        return "archived_live"
    return "uploaded"


def _audience(text: str, made_for_kids: bool | None, age_restricted: bool) -> dict:
    if made_for_kids:
        target_age, confidence = ["children"], 1.0
    elif age_restricted:
        target_age, confidence = ["adult", "mature"], 1.0
    else:
        target_age = _match_labels(text, AGE_RULES, 2)
        confidence = min(0.9, 0.45 + 0.2 * len(target_age)) if target_age else 0.0
        target_age = target_age or ["unknown"]

    lowered = text.lower()
    female = sum(term.lower() in lowered for term in FEMALE_TERMS)
    male = sum(term.lower() in lowered for term in MALE_TERMS)
    if female and male:
        orientation, orientation_confidence = "mixed", min(0.9, 0.5 + 0.1 * (female + male))
    elif female:
        orientation, orientation_confidence = "female_oriented", min(0.9, 0.5 + 0.1 * female)
    elif male:
        orientation, orientation_confidence = "male_oriented", min(0.9, 0.5 + 0.1 * male)
    else:
        orientation, orientation_confidence = "general", 0.35
    return {
        "made_for_kids": made_for_kids,
        "age_restricted": age_restricted,
        "target_age": target_age,
        "target_age_confidence": round(confidence, 2),
        "orientation": orientation,
        "orientation_confidence": round(orientation_confidence, 2),
        "basis": "official_flags_plus_explicit_content_heuristics",
    }


def _popularity(views: int | None, likes: int | None, comments: int | None, subscribers: int | None, age_hours: float | None) -> dict:
    view_value = max(0, views or 0)
    views_per_hour = view_value / max(1.0, age_hours) if views is not None and age_hours is not None else None
    likes_per_1000 = (max(0, likes or 0) / view_value * 1000) if view_value and likes is not None else None
    comments_per_1000 = (max(0, comments or 0) / view_value * 1000) if view_value and comments is not None else None
    views_per_subscriber = (view_value / subscribers) if views is not None and subscribers else None
    components: list[tuple[float, float]] = []
    if views_per_hour is not None:
        components.append((min(1.0, math.log10(views_per_hour + 1) / 4.5), 0.45))
    if likes_per_1000 is not None:
        components.append((min(1.0, likes_per_1000 / 80.0), 0.25))
    if comments_per_1000 is not None:
        components.append((min(1.0, comments_per_1000 / 12.0), 0.15))
    if views_per_subscriber is not None:
        components.append((min(1.0, views_per_subscriber / 1.5), 0.15))
    total_weight = sum(weight for _, weight in components)
    score = sum(value * weight for value, weight in components) / total_weight if total_weight else 0.0
    label = "viral" if score >= 0.85 else "hot" if score >= 0.65 else "active" if score >= 0.4 else "normal"
    return {
        "views": views,
        "likes": likes,
        "comments": comments,
        "subscribers": subscribers,
        "views_per_hour": round(views_per_hour, 2) if views_per_hour is not None else None,
        "likes_per_1000_views": round(likes_per_1000, 2) if likes_per_1000 is not None else None,
        "comments_per_1000_views": round(comments_per_1000, 2) if comments_per_1000 is not None else None,
        "views_per_subscriber": round(views_per_subscriber, 3) if views_per_subscriber is not None else None,
        "hype_score": round(score, 3),
        "hype_label": label,
        "hype_basis": "single_snapshot_proxy",
    }


def build_generation_context(
    reference_text: str,
    *,
    youtube_context: Any | None = None,
    additional_context: str | None = None,
    category_hint: str | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    combined = "\n".join(part for part in (reference_text, additional_context or "") if part).strip()
    topics = _match_labels(combined, TOPIC_RULES, 8)
    styles = _match_labels(combined, STYLE_RULES, 6)
    if category_hint == "vlog" and "vlog" not in styles:
        styles.insert(0, "vlog")
    elif category_hint and category_hint not in {"auto", "social", "vlog"}:
        normalized_hint = category_hint.strip().lower().replace(" ", "_")
        if normalized_hint and normalized_hint not in topics:
            topics.insert(0, normalized_hint)

    published_at = getattr(youtube_context, "published_at", None) if youtube_context else None
    published = _parse_datetime(published_at)
    age_hours = max(0.0, (now - published.astimezone(timezone.utc)).total_seconds() / 3600) if published else None

    if youtube_context:
        source = {
            "type": "youtube",
            "title": getattr(youtube_context, "title", ""),
            "description": getattr(youtube_context, "description", "")[:4000],
            "transcript_excerpt": (getattr(youtube_context, "transcript", None) or "")[:6000],
            "language": getattr(youtube_context, "default_language", None) or getattr(youtube_context, "transcript_language", None),
            "additional_context": additional_context or None,
        }
        youtube = {
            "video_id": getattr(youtube_context, "video_id", None),
            "category_id": getattr(youtube_context, "category_id", None),
            "category_name": getattr(youtube_context, "category_name", None),
            "topic_categories": list(getattr(youtube_context, "topic_categories", ()) or ()),
            "tags": list(getattr(youtube_context, "tags", ()) or ())[:40],
        }
        format_context = {
            "kind": _format_kind(getattr(youtube_context, "duration_seconds", None), getattr(youtube_context, "is_short", None)),
            "broadcast": _broadcast_kind(getattr(youtube_context, "live_broadcast_content", None), getattr(youtube_context, "live_streaming_details", None)),
            "duration_seconds": getattr(youtube_context, "duration_seconds", None),
        }
        audience = _audience(combined, getattr(youtube_context, "made_for_kids", None), bool(getattr(youtube_context, "age_restricted", False)))
        popularity = _popularity(
            getattr(youtube_context, "view_count", None),
            getattr(youtube_context, "like_count", None),
            getattr(youtube_context, "comment_count", None),
            getattr(youtube_context, "subscriber_count", None),
            age_hours,
        )
    else:
        source = {
            "type": "manual",
            "title": next((line.strip() for line in reference_text.splitlines() if line.strip()), "")[:200],
            "description": reference_text[:4000],
            "transcript_excerpt": "",
            "language": "ko" if re.search(r"[가-힣]", combined) else None,
            "additional_context": additional_context or None,
        }
        youtube = {"video_id": None, "category_id": None, "category_name": None, "topic_categories": [], "tags": []}
        format_context = {"kind": "unknown", "broadcast": "unknown", "duration_seconds": None}
        audience = _audience(combined, None, False)
        popularity = _popularity(None, None, None, None, None)

    temporal = {
        "published_at": published_at,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "freshness": _freshness(age_hours),
        "weekday": published.strftime("%A").lower() if published else None,
        "month": published.month if published else None,
        "season": _season(published.month if published else None),
    }
    historical = build_historical_profile(combined, topics=topics, content_styles=styles)
    primary = youtube.get("category_name") or (category_hint if category_hint and category_hint not in {"auto", "social"} else None) or (topics[0] if topics else "Other")
    return {
        "source": source,
        "youtube": youtube,
        "format": format_context,
        "audience": audience,
        "temporal": temporal,
        "popularity": popularity,
        "content": {"keywords": _extract_keywords(combined), "topics": topics, "content_styles": styles},
        "historical_comments": historical,
        "primary_category": primary,
        "context_version": "1.0",
    }


def summarize_generation_context(context: dict) -> dict:
    youtube = context.get("youtube") or {}
    content = context.get("content") or {}
    format_context = context.get("format") or {}
    temporal = context.get("temporal") or {}
    popularity = context.get("popularity") or {}
    historical = context.get("historical_comments") or {}
    return {
        "primary_category": context.get("primary_category", "Other"),
        "official_category": youtube.get("category_name"),
        "topics": list(content.get("topics") or [])[:6],
        "content_styles": list(content.get("content_styles") or [])[:5],
        "format": format_context.get("kind", "unknown"),
        "broadcast": format_context.get("broadcast", "unknown"),
        "freshness": temporal.get("freshness", "unknown"),
        "hype_label": popularity.get("hype_label", "normal"),
        "hype_score": popularity.get("hype_score", 0.0),
        "historical_match_count": historical.get("matched_count", 0),
        "historical_coverage": historical.get("coverage", "none"),
    }
