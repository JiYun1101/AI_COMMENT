from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
ISO8601_DURATION_RE = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)
MAX_DESCRIPTION_CHARS = 4_000


class YouTubeContextError(Exception):
    """Base error for YouTube reference-context lookup failures."""


class InvalidYouTubeUrlError(YouTubeContextError):
    pass


class YouTubeConfigurationError(YouTubeContextError):
    pass


class YouTubeLookupError(YouTubeContextError):
    pass


@dataclass(frozen=True)
class YouTubeVideoContext:
    video_id: str
    url: str
    title: str
    description: str
    channel: str
    subscriber_count: int | None
    view_count: int | None
    published_at: str | None
    duration_seconds: int | None
    thumbnail_url: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def extract_video_id(url: str) -> str:
    """Extract an 11-character YouTube video id from common URL shapes."""
    raw = url.strip()
    if not raw:
        raise InvalidYouTubeUrlError("YouTube URL이 비어 있습니다.")

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc.lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]

    video_id: str | None = None

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
                video_id = parts[1]

    if not video_id or not VIDEO_ID_RE.fullmatch(video_id):
        raise InvalidYouTubeUrlError("지원되는 YouTube 영상 URL이 아닙니다.")

    return video_id


def parse_duration_seconds(value: str | None) -> int | None:
    if not value:
        return None
    match = ISO8601_DURATION_RE.fullmatch(value)
    if not match:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


def _api_get(session, path: str, params: dict, api_key: str) -> dict:
    try:
        response = session.get(
            f"{YOUTUBE_API_BASE}/{path}",
            params={**params, "key": api_key},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise YouTubeLookupError("YouTube API에 연결할 수 없습니다.") from exc

    if response.status_code != 200:
        detail = response.text[:240] if getattr(response, "text", None) else ""
        raise YouTubeLookupError(
            f"YouTube API 조회에 실패했습니다 ({response.status_code}). {detail}".strip()
        )

    try:
        return response.json()
    except ValueError as exc:
        raise YouTubeLookupError("YouTube API 응답을 해석할 수 없습니다.") from exc


def _best_thumbnail(snippet: dict) -> str | None:
    thumbnails = snippet.get("thumbnails") or {}
    for key in ("maxres", "standard", "high", "medium", "default"):
        url = (thumbnails.get(key) or {}).get("url")
        if url:
            return url
    return None


def fetch_youtube_context(
    url: str,
    *,
    api_key: str | None = None,
    session=None,
) -> YouTubeVideoContext:
    video_id = extract_video_id(url)
    key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise YouTubeConfigurationError("YOUTUBE_API_KEY가 설정되어 있지 않습니다.")

    http = session or requests.Session()
    video_payload = _api_get(
        http,
        "videos",
        {
            "part": "snippet,contentDetails,statistics",
            "id": video_id,
        },
        key,
    )
    items = video_payload.get("items") or []
    if not items:
        raise YouTubeLookupError("해당 YouTube 영상을 찾을 수 없습니다.")

    video = items[0]
    snippet = video.get("snippet") or {}
    statistics = video.get("statistics") or {}
    content_details = video.get("contentDetails") or {}

    subscriber_count: int | None = None
    channel_id = snippet.get("channelId")
    if channel_id:
        channel_payload = _api_get(
            http,
            "channels",
            {"part": "statistics", "id": channel_id},
            key,
        )
        channel_items = channel_payload.get("items") or []
        if channel_items:
            channel_stats = channel_items[0].get("statistics") or {}
            if not channel_stats.get("hiddenSubscriberCount"):
                raw_subscriber_count = channel_stats.get("subscriberCount")
                if raw_subscriber_count is not None:
                    subscriber_count = int(raw_subscriber_count)

    raw_view_count = statistics.get("viewCount")
    view_count = int(raw_view_count) if raw_view_count is not None else None

    return YouTubeVideoContext(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=(snippet.get("title") or "").strip(),
        description=(snippet.get("description") or "").strip(),
        channel=(snippet.get("channelTitle") or "").strip(),
        subscriber_count=subscriber_count,
        view_count=view_count,
        published_at=snippet.get("publishedAt"),
        duration_seconds=parse_duration_seconds(content_details.get("duration")),
        thumbnail_url=_best_thumbnail(snippet),
    )


def build_reference_text(context: YouTubeVideoContext) -> str:
    """Create the text that existing lexical/embedding ranking features consume."""
    parts = [f"제목: {context.title}"]
    if context.channel:
        parts.append(f"채널: {context.channel}")
    if context.description:
        description = context.description[:MAX_DESCRIPTION_CHARS]
        parts.append(f"설명: {description}")
    return "\n".join(parts)
