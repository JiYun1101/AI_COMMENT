"""All generated recommendations omit laughter markers, emoji and emoticons."""
from __future__ import annotations

import re

FORMAL_PERSONAS = {"polite_viewer", "calm_analyst"}
STYLES = {"standard", "casual_imperfect"}
EMOJI = re.compile("[\U0001F1E6-\U0001FAFF\u2600-\u27BF\uFE0E\uFE0F\u200D\u20E3]")
LAUGHTER = re.compile(r"ㅋ+|ㅎ{2,}|\b(?:lol|lmao|rofl|haha|hehe)\b", re.I)
EMOTICON = re.compile(
    r"\^[_-]?\^|>[_-]<|ㅠ{2,}|ㅜ{2,}|(?<!\w)[:;=8][-^]?[)(DPp](?!\w)|(?<!\w)<3(?!\w)"
)
CHAT = re.compile(
    r"(?:^|\s)(?:걍|갠적(?:으론|으로)?|먼가|왜케|왤케|넘|담엔|담에|ㄹㅇ|"
    r"ㄱㅊ|ㅇㅈ|ㅇㅇ|머임|머지|이거진짜)(?:\s|$)"
    r"|(?:임|함|한듯|인듯|이네여)(?:\s|$)"
)


def clean_comment(text: str) -> str:
    """100% removal of expressive marks; retain readable spaces and questions."""
    cleaned = str(text or "")
    cleaned = EMOJI.sub("", cleaned)
    cleaned = EMOTICON.sub("", cleaned)
    cleaned = LAUGHTER.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return re.sub(r"[.!！。．…~]+$", "", cleaned).strip()


def detect_style(text: str, label: str | None = None) -> str:
    if label in STYLES:
        return label
    return "casual_imperfect" if CHAT.search(text.strip()) else "standard"


def casual_target(count: int, persona: dict | None = None) -> int:
    if (persona or {}).get("id") in FORMAL_PERSONAS:
        return 0
    return max(0, count // 2)
