"""Clean decorative noise and track Korean writing styles without forced text mutation."""
from __future__ import annotations
import re

FORMAL_PERSONAS = {"polite_viewer", "calm_analyst"}
STYLES = {"standard", "casual_imperfect"}
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")
CHAT = re.compile(
    r"(?:^|\s)(?:걍|갠적(?:으론|으로)?|먼가|왜케|왤케|넘|담엔|담에|ㄹㅇ|"
    r"ㄱㅊ|ㅇㅈ|ㅇㅇ|머임|머지|이거진짜)(?:\s|$)"
    r"|(?:임|함|한듯|인듯|이네여)(?:\s|$)"
)


def clean_comment(text: str) -> str:
    cleaned = EMOJI.sub("", str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"ㅋ{3,}", "ㅋㅋ", cleaned)
    cleaned = re.sub(r"ㅎ{3,}", "ㅎㅎ", cleaned)
    return re.sub(r"[.!！。．…~]+$", "", cleaned).strip()


def detect_style(text: str, label: str | None = None) -> str:
    if label in STYLES:
        return label
    return "casual_imperfect" if CHAT.search(text.strip()) else "standard"


def casual_target(count: int, persona: dict | None = None) -> int:
    if (persona or {}).get("id") in FORMAL_PERSONAS:
        return 0
    return max(0, count // 2)
