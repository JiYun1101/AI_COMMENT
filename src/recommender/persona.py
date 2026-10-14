from __future__ import annotations

from typing import Literal, TypedDict

PersonaId = Literal[
    "none",
    "polite_viewer",
    "friendly_viewer",
    "warm_supporter",
    "calm_analyst",
    "playful_casual",
]


class PersonaDirective(TypedDict):
    id: str
    name: str
    formality: str
    tone: str
    markers: str
    length: str
    rules: list[str]


PERSONAS: dict[str, PersonaDirective] = {
    "polite_viewer": {
        "id": "polite_viewer",
        "name": "정중한 시청자",
        "formality": "합쇼체",
        "tone": "차분",
        "markers": "없음",
        "length": "길게",
        "rules": [
            "Use formal Korean 합쇼체 endings such as ~습니다/~합니다 when writing Korean.",
            "Keep the emotional tone calm and composed.",
            "Do not use emoji, ㅋㅋ, or decorative exclamation marks.",
            "Prefer a relatively detailed comment while staying natural and under the product length limit.",
        ],
    },
    "friendly_viewer": {
        "id": "friendly_viewer",
        "name": "친근한 시청자",
        "formality": "해요체",
        "tone": "응원",
        "markers": "조금",
        "length": "자동",
        "rules": [
            "Use friendly Korean 해요체 when writing Korean.",
            "Keep the tone supportive and approachable.",
            "Use emoji, ㅋㅋ, or exclamation marks sparingly, only when natural.",
            "Follow the surrounding/historical comment length rather than forcing a short or long comment.",
        ],
    },
    "warm_supporter": {
        "id": "warm_supporter",
        "name": "따뜻한 응원형",
        "formality": "해요체",
        "tone": "응원",
        "markers": "조금",
        "length": "짧게",
        "rules": [
            "Use warm Korean 해요체 when writing Korean.",
            "Prioritize supportive, encouraging emotional tone.",
            "Use emoji or exclamation marks sparingly, only when natural.",
            "Keep comments concise.",
        ],
    },
    "calm_analyst": {
        "id": "calm_analyst",
        "name": "차분한 분석형",
        "formality": "해요체",
        "tone": "차분",
        "markers": "없음",
        "length": "길게",
        "rules": [
            "Use calm Korean 해요체 when writing Korean.",
            "Prefer specific observations, reasoning, or grounded questions over generic praise.",
            "Do not use emoji, ㅋㅋ, or decorative exclamation marks.",
            "Prefer a relatively detailed comment while staying natural and under the product length limit.",
        ],
    },
    "playful_casual": {
        "id": "playful_casual",
        "name": "유쾌한 캐주얼",
        "formality": "반말",
        "tone": "유머",
        "markers": "풍부",
        "length": "짧게",
        "rules": [
            "Use casual Korean 반말 when writing Korean.",
            "Keep the tone playful and light, without insulting or harassing anyone.",
            "Emoji, ㅋㅋ, and exclamation marks may be used more freely when natural.",
            "Keep comments short and punchy.",
        ],
    },
}


def resolve_persona(persona_id: str | None) -> PersonaDirective | None:
    normalized = (persona_id or "none").strip()
    if normalized == "none":
        return None
    return PERSONAS.get(normalized)


FORBIDDEN_MARKS = {
    "period": ".。．",
    "exclamation": "!！",
    "question": "?？",
    "comma": ",，",
    "tilde": "~～",
}


def build_custom_persona(data: dict) -> dict:
    """Validate user-provided style metadata, never turn it into system rules."""
    name = str(data.get("name") or "").strip()
    style = str(data.get("speech_style") or "").strip()
    example = str(data.get("sample_comment") or "").strip()
    if not name or len(name) > 40 or len(style) > 240 or len(example) > 200:
        raise ValueError("페르소나 이름과 말투 제한의 길이를 확인해주세요.")

    def phrases(key: str) -> list[str]:
        values = data.get(key) or []
        if not isinstance(values, list) or len(values) > 8:
            raise ValueError("표현은 항목별로 최대 8개까지 입력할 수 있습니다.")
        cleaned = []
        for item in values:
            if not isinstance(item, str) or not item.strip() or len(item.strip()) > 60:
                raise ValueError("표현은 항목당 1~60자로 입력해주세요.")
            if item.strip() not in cleaned:
                cleaned.append(item.strip())
        return cleaned

    allowed = set(FORBIDDEN_MARKS) | {"emoji", "laughter"}
    marks = data.get("forbidden_marks") or []
    if not isinstance(marks, list) or len(marks) > len(allowed) or any(mark not in allowed for mark in marks):
        raise ValueError("지원하지 않는 문장부호 제한입니다.")
    return {
        "id": data["id"],
        "name": name,
        "user_defined": True,
        "speech_style": style,
        "recurring_phrases": phrases("recurring_phrases"),
        "prohibited_phrases": phrases("prohibited_phrases"),
        "forbidden_marks": list(dict.fromkeys(marks)),
        "sample_comment": example,
        "formality": "사용자 설정",
        "tone": "사용자 설정",
        "markers": "사용자 설정",
        "length": "자동",
        "rules": [],
    }


def custom_persona_violation(comment: str, persona: dict | None) -> str | None:
    """Hard-stop forbidden expressions/marks even if a model ignores the prompt."""
    if not persona or not persona.get("user_defined"):
        return None
    folded = comment.casefold()
    for expression in persona.get("prohibited_phrases") or []:
        if expression.casefold() in folded:
            return f"페르소나 금지 표현: {expression}"
    for mark in persona.get("forbidden_marks") or []:
        if mark == "laughter":
            import re
            if re.search(r"(?:ㅋ{1,}|ㅎ{2,})", comment):
                return "페르소나 금지: 웃음 표현"
        elif mark == "emoji":
            from src.recommender.writing_style import EMOJI
            if EMOJI.search(comment):
                return "페르소나 금지: 이모지"
        elif mark in FORBIDDEN_MARKS and any(char in comment for char in FORBIDDEN_MARKS[mark]):
            return f"페르소나 금지 문장부호: {mark}"
    return None
