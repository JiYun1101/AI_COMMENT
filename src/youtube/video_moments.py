"""Caption-time evidence for the first video-understanding milestone.

This is *not* computer vision. It makes time-aligned, auditable caption
segments available to future visual and multimodal agents without hallucinating
any scene or making thumbnail pixels into video frames.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Callable, Iterable

from src.youtube.context import VIDEO_ID_RE

MAX_CAPTIONS = 1200
MAX_MOMENTS = 12
WINDOW_SECONDS = 60
MAX_CHARS_PER_MOMENT = 650


def _caption_value(caption: Any, field: str) -> Any:
    return caption.get(field) if isinstance(caption, dict) else getattr(caption, field, None)


def group_caption_moments(
    captions: Iterable[Any], *, window_seconds: int = WINDOW_SECONDS,
    max_moments: int = MAX_MOMENTS,
) -> list[dict]:
    """Group real timed captions into windows and sample across full duration."""
    windows: dict[int, list[str]] = defaultdict(list)
    for idx, item in enumerate(captions):
        if idx >= MAX_CAPTIONS:
            break
        start = _caption_value(item, "start")
        value = _caption_value(item, "text")
        if isinstance(start, bool) or not isinstance(start, (float, int)):
            continue
        if start < 0 or not isinstance(value, str):
            continue
        content = re.sub(r"\s+", " ", value).strip()
        if not content:
            continue
        index = int(start // window_seconds)
        existing = sum(len(x) + 1 for x in windows[index])
        if existing < MAX_CHARS_PER_MOMENT:
            windows[index].append(content[:MAX_CHARS_PER_MOMENT - existing])
    all_moments = [
        {"start_seconds": window * window_seconds,
         "end_seconds": (window + 1) * window_seconds,
         "text": " ".join(windows[window]),
         "source": "captions"}
        for window in sorted(windows)
    ]
    if len(all_moments) <= max_moments:
        return all_moments
    # Even coverage across the video rather than only the beginning.
    selected = sorted({
        round(i * (len(all_moments) - 1) / (max_moments - 1))
        for i in range(max_moments)
    })
    return [all_moments[i] for i in selected]


def _fetch_timed_captions(video_id: str) -> tuple[Iterable[Any], str | None]:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    try:
        result = api.fetch(video_id, languages=("ko", "en"))
        return getattr(result, "snippets", result), getattr(result, "language_code", None)
    except Exception:
        transcripts = api.list(video_id)
        transcript = next(iter(transcripts), None)
        if transcript is None:
            return [], None
        fetched = transcript.fetch()
        return getattr(fetched, "snippets", fetched), getattr(transcript, "language_code", None)


def get_video_caption_moments(
    video_id: str, *, fetcher: Callable[[str], tuple[Iterable[Any], str | None]] | None = None,
) -> dict:
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise ValueError("올바른 YouTube 영상 ID가 아닙니다.")
    source = fetcher or _fetch_timed_captions
    try:
        captions, language = source(video_id)
        moments = group_caption_moments(captions)
    except Exception as exc:
        unavailable = exc.__class__.__name__ in {
            "TranscriptsDisabled", "NoTranscriptFound", "NoTranscriptAvailable",
        }
        return {
            "video_id": video_id,
            "status": "unavailable" if unavailable else "fetch_failed",
            "language": None, "evidence": "captions_only", "frames_analyzed": False,
            "moments": [],
            "warning": "자막을 가져올 수 없습니다. 영상 장면을 추측하지 않습니다.",
        }
    return {
        "video_id": video_id, "status": "available" if moments else "unavailable",
        "language": language, "evidence": "captions_only", "frames_analyzed": False,
        "moments": moments,
        "warning": "자막 타임라인입니다. 화면 속 인물·행동·장면은 아직 분석하지 않았습니다.",
    }
