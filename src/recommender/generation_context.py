from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from src.recommender.historical_comments import build_historical_profile

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9+#.-]{2,}")
_STOPWORDS = {
    "그리고", "하지만", "그래서", "이번", "영상", "대한", "대해", "관련", "내용", "정리",
    "이야기", "합니다", "했습니다", "있는", "없는", "하는", "되는", "것", "수", "더", "제목",
    "채널", "설명", "자막", "스크립트", "the", "and", "for", "with", "this", "that", "from",
    "about", "video", "youtube", "into", "your", "you", "are", "was", "were", "have", "has",
    "had", "how", "why", "what", "when", "where", "who", "which", "will", "can", "could", "would",
    "should", "not", "but", "all", "new", "out", "our", "their", "they", "them", "its", "it's", "to",
    "of", "in", "on", "at", "by", "is", "it", "as", "an", "a", "be", "or", "if", "we", "i", "my",
}

TOPIC_RULES: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "인공지능", "llm", "gpt", "machine learning", "머신러닝", "딥러닝"),
    "software": ("개발자", "프로그래밍", "코딩", "software", "frontend", "backend", "react", "python", "javascript"),
    "hardware": ("cpu", "gpu", "반도체", "hardware", "pc", "컴퓨터", "노트북"),
    "mobile": ("스마트폰", "갤럭시", "아이폰", "iphone", "android", "fold", "모바일"),
    "science": ("과학", "science", "연구", "실험", "우주", "물리", "화학", "생물"),
    "technology": ("기술", "technology", "tech", "로봇", "robot", "산업"),
    "career": ("커리어", "취업", "이직", "면접", "직장", "회사", "career", "job"),
    "education": ("교육", "공부", "수능", "학교", "대학", "강의", "tutorial", "course"),
    "finance": ("주식", "투자", "금리", "재테크", "finance", "stock", "crypto", "코인"),
    "economy": ("경제", "물가", "경기", "부동산", "economy", "inflation"),
    "politics": ("정치", "대통령", "정부", "국회", "선거", "politics", "election"),
    "law": ("법", "법률", "규제", "정책", "제도", "law", "regulation"),
    "beauty": ("메이크업", "화장품", "스킨케어", "뷰티", "beauty", "makeup", "cosmetic"),
    "fashion": ("패션", "코디", "옷", "fashion", "style", "outfit"),
    "food": ("맛집", "먹방", "요리", "레시피", "음식", "food", "recipe", "restaurant"),
    "travel": ("여행", "관광", "호텔", "제주", "서울", "부산", "travel", "trip", "vlog abroad"),
    "fitness": ("운동", "헬스", "러닝", "클라이밍", "fitness", "workout", "gym"),
    "health": ("건강", "의학", "병원", "영양", "health", "medical", "diet"),
    "relationships": ("연애", "데이트", "결혼", "관계", "relationship", "dating"),
    "music": ("음악", "노래", "가수", "뮤직비디오", "music", "song", "album", "mv"),
    "film": ("영화", "드라마", "배우", "film", "movie", "cinema", "series"),
    "animation": ("애니", "애니메이션", "animation", "anime"),
    "gaming": ("게임", "게이밍", "game", "gaming", "플레이", "공략"),
    "sports": ("스포츠", "축구", "야구", "농구", "테니스", "sports", "football", "baseball", "basketball"),
    "animals": ("고양이", "강아지", "반려동물", "동물", "cat", "dog", "pet", "animal"),
    "autos": ("자동차", "차량", "전기차", "car", "vehicle", "tesla", "현대차"),
    "lifestyle": ("일상", "루틴", "자취", "브이로그", "daily", "routine", "vlog"),
    "shopping": ("쇼핑", "구매", "haul", "shopping", "세일", "추천템"),
    "news": ("뉴스", "속보", "오늘", "news", "breaking"),
}

STYLE_RULES: dict[str, tuple[str, ...]] = {
    "educational": ("강의", "설명", "배우", "알아보", "정리", "교육", "lecture", "explained", "learn"),
    "tutorial": ("방법", "하는 법", "가이드", "튜토리얼", "tutorial", "how to", "guide"),
    "review": ("리뷰", "후기", "사용기", "review", "hands-on"),
    "comparison": ("비교", "vs", "대결", "comparison", "versus"),
    "discussion": ("토론", "논의", "이야기", "discussion", "debate"),
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
    "young_adult": ("대학생", "취준", "신입", "자취", "20대", "college", "student", "entry level"),
    "adult": ("직장인", "육아", "결혼", "부모", "30대", "40대", "직장", "adult"),
    "mature": ("중년", "은퇴", "노후", "50대", "60대", "senior", "retirement"),
}

FEMALE_ORIENTATION_TERMS = ("여성", "여자", "여대생", "여친", "여성용", "women", "woman", "girl", "여자 코디")
MALE_ORIENTATION_TERMS = ("남성", "남자", "남친", "남성용", "men", "man", "boy", "남자 코디")


def _contains(text: str, keyword: str) -> bool:
    return keyword.lower() in text.lower()


def _extract_keywords(text: str, limit: int = 12) -> list[str]:
    ordered: list[str] = []
    counts: dict[str, int] = {}
    for raw in _TOKEN_RE.findall(text or ""):
        token = raw.strip(".-").lower()
        if len(token) < 2 or token in _STOPWORDS or token.isdigit():
            continue
        if token not in counts:
            ordered.append(token)
            counts[token] = 0
        counts[token] += 1
    ordered.sort(key=lambda token: (-counts[token], ordered.index(token)))
    return ordered[:limit]


def _match_labels(text: str, rules: dict[str, tuple[str, ...]], *, limit: int | None = None) -> list[str]:
    matches: list[tuple[int, str]] = []
    lowered = text.lower()
    for label, keywords in rules.items():
        score = sum(1 for keyword in keywords if keyword.lower() in lowered)
        if score:
            matches.append((score, label))
    matches.sort(key=lambda item: (-item[0], item[1]))
    labels = [label for _, label in matches]
    return labels[:limit] if limit is not None else labels


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _freshness(age_hours: float | None) -> str:
    if age_hours is None:
        return "unknown"
    if age_hours < 24:
        return "breaking"
    if age_hours < 72:
        return "fresh"
    if age_hours < 24 * 7:
        return "recent"
    if age_hours < 24 * 30:
        return "current"
    if age_hours < 24 * 30 * 6:
        return "established"
    if age_hours < 24 * 365 * 2:
        return "old"
    return "evergreen"


def _season(month: int | None) -> str | None:
    if month is None:
        return None
    if month in {3, 4, 5}:
        return "spring"
    if month in {6, 7, 8}:
        return "summer"
    if month in {9, 10, 11}:
        return "autumn"
    return "winter"


def _format_kind(duration_seconds: int | None, is_short: bool | None) -> str:
    if is_short:
        return "short"
    if duration_seconds is None:
        return "unknown"
    if duration_seconds <= 180:
        return "short_like"
    if duration_seconds >= 20 * 60:
        return "long_form"
    return "standard"


def _broadcast_kind(live_broadcast_content: str | None, live_streaming_details: dict[str, Any] | None) -> str:
    value = (live_broadcast_content or "none").lower()
    details = live_streaming_details or {}
    if value == "live":
        return "live"
    if value == "upcoming":
        return "upcoming"
    if details.get("actualStartTime") or details.get("actualEndTime"):
        return "archived_live"
    return "uploaded"


def _audience(text: str, made_for_kids: bool | None, age_restricted: bool) -> dict:
    if made_for_kids:
        target_age = ["children"]
        age_confidence = 1.0
    elif age_restricted:
        target_age = ["adult", "mature"]
        age_confidence = 1.0
    else:
        target_age = _match_labels(text, AGE_RULES, limit=2)
        age_confidence = min(0.9, 0.45 + 0.2 * len(target_age)) if target_age else 0.0
        if not target_age:
            target_age = ["unknown"]

    lowered = text.lower()
    female = sum(1 for keyword in FEMALE_ORIENTATION_TERMS if keyword.lower() in lowered)
    male = sum(1 for keyword in MALE_ORIENTATION_TERMS if keyword.lower() in lowered)
    if female and male:
        orientation = "mixed"
        orientation_confidence = min(0.9, 0.5 + 0.1 * (female + male))
    elif female:
        orientation = "female_oriented"
        orientation_confidence = min(0.9, 0.5 + 0.1 * female)
    elif male:
        orientation = "male_oriented"
        orientation_confidence = min(0.9, 0.5 + 0.1 * male)
    else:
        orientation = "general"
        orientation_confidence = 0.35

    return {
        "made_for_kids": made_for_kids,
        "age_restricted": age_restricted,
        "target_age": target_age,
        "target_age_confidence": round(age_confidence, 2),
        "orientation": orientation,
        "orientation_confidence": round(orientation_confidence, 2),
        "basis": "official_flags_plus_explicit_content_heuristics",
    }


def _popularity(*, views: int | None, likes: int | None, comments: int | None, subscribers: int | None, age_hours: float | None) -> dict:
    views_value = max(0, views or 0)
    likes_value = max(0, likes or 0)
    comments_value = max(0, comments or 0)
    subscribers_value = max(0, subscribers or 0)
    effective_hours = max(1.0, age_hours or 1.0)

    views_per_hour = views_value / effective_hours if views is not None and age_hours is not None else None
    likes_per_1000 = (likes_value / views_value * 1000) if views_value and likes is not None else None
    comments_per_1000 = (comments_value / views_value * 1000) if views_value and comments is not None else None
    views_per_subscriber = (views_value / subscribers_value) if subscribers_value and views is not None else None

    components: list[tuple[float, float]] = []
    if views_per_hour is not None:
        components.append((min(1.0, math.log10(views_per_hour + 1) / 4.5), 0.45))
    if likes_per_1000 is not None:
        components.append((min(1.0, likes_per_1000 / 80.0), 0.25))
    if comments_per_1000 is not None:
        components.append((min(1.0, comments_per_1000 / 12.0), 0.15))
    if views_per_subscriber is not None:
        components.append((min(1.0, views_per_subscriber / 1.5), 0.15))

    if components:
        weight_sum = sum(weight for _, weight in components)
        hype_score = sum(value * weight for value, weight in components) / weight_sum
    else:
        hype_score = 0.0

    if hype_score >= 0.85:
        hype_label = "viral"
    elif hype_score >= 0.65:
        hype_label = "hot"
    elif hype_score >= 0.4:
        hype_label = "active"
    else:
        hype_label = "normal"

    return {
        "views": views,
        "likes": likes,
        "comments": comments,
        "subscribers": subscribers,
        "views_per_hour": round(views_per_hour, 2) if views_per_hour is not None else None,
        "likes_per_1000_views": round(likes_per_1000, 2) if likes_per_1000 is not None else None,
        "comments_per_1000_views": round(comments_per_1000, 2) if comments_per_1000 is not None else None,
        "views_per_subscriber": round(views_per_subscriber, 3) if views_per_subscriber is not None else None,
        "hype_score": round(hype_score, 3),
        "hype_label": hype_label,
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
    combined_text = "\n".join(part for part in (reference_text, additional_context or "") if part).strip()
    keywords = _extract_keywords(combined_text)
    topics = _match_labels(combined_text, TOPIC_RULES, limit=8)
    content_styles = _match_labels(combined_text, STYLE_RULES, limit=6)

    if category_hint and category_hint not in {"auto", "social", "vlog"}:
        topics = [category_hint.strip().lower().replace(" ", "_"), *topics]
    elif category_hint == "vlog" and "vlog" not in content_styles:
        content_styles.insert(0, "vlog")

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
            "broadcast": _broadcast_kind(
                getattr(youtube_context, "live_broadcast_content", None),
                getattr(youtube_context, "live_streaming_details", None),
            ),
            "duration_seconds": getattr(youtube_context, "duration_seconds", None),
        }
        audience = _audience(
            combined_text,
            getattr(youtube_context, "made_for_kids", None),
            bool(getattr(youtube_context, "age_restricted", False)),
        )
        popularity = _popularity(
            views=getattr(youtube_context, "view_count", None),
            likes=getattr(youtube_context, "like_count", None),
            comments=getattr(youtube_context, "comment_count", None),
            subscribers=getattr(youtube_context, "subscriber_count", None),
            age_hours=age_hours,
        )
    else:
        source = {
            "type": "manual",
            "title": (reference_text.strip().splitlines() or [""])[0][:200],
            "description": reference_text[:4000],
            "transcript_excerpt": "",
            "language": "ko" if re.search(r"[가-힣]", combined_text) else None,
            "additional_context": additional_context or None,
        }
        youtube = {
            "video_id": None,
            "category_id": None,
            "category_name": None,
            "topic_categories": [],
            "tags": [],
        }
        format_context = {"kind": "unknown", "broadcast": "unknown", "duration_seconds": None}
        audience = _audience(combined_text, None, False)
        popularity = _popularity(views=None, likes=None, comments=None, subscribers=None, age_hours=None)

    temporal = {
        "published_at": published_at,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "freshness": _freshness(age_hours),
        "weekday": published.strftime("%A").lower() if published else None,
        "month": published.month if published else None,
        "season": _season(published.month if published else None),
    }

    historical = build_historical_profile(
        combined_text,
        topics=topics,
        content_styles=content_styles,
    )

    official_category = youtube.get("category_name")
    if official_category:
        primary_category = official_category
    elif category_hint and category_hint not in {"auto", "social"}:
        primary_category = category_hint
    elif topics:
        primary_category = topics[0]
    else:
        primary_category = "Other"

    return {
        "source": source,
        "youtube": youtube,
        "format": format_context,
        "audience": audience,
        "temporal": temporal,
        "popularity": popularity,
        "content": {
            "keywords": keywords,
            "topics": topics,
            "content_styles": content_styles,
        },
        "historical_comments": historical,
        "primary_category": primary_category,
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
