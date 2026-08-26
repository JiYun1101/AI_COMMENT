"""LLM 제공자 공통 계층.

여러 제공자(OpenAI Responses API, 로컬 Ollama)가 같은 계약을 공유하도록
에러 타입 · 응답 JSON 파싱 · 후보 검증을 한곳에 모은다.

제공자 클라이언트는 모두 아래 인터페이스를 만족해야 한다::

    client.generate(generation_context: dict, *, candidate_count: int) -> list[dict]

``src/recommender/candidate_generator.py`` 가 이 인터페이스에만 의존하므로,
제공자를 바꿔도 추천 파이프라인은 그대로 동작한다.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

ALLOWED_TYPES = {"insight", "empathy", "question", "casual", "general"}


class LLMNotReadyError(RuntimeError):
    """LLM 설정(모델명·API 키 등)이 갖춰지지 않은 상태."""


class LLMGenerationError(RuntimeError):
    """LLM 호출 또는 응답 해석에 실패한 상태."""


def extract_json(text: str) -> Any:
    """LLM 응답 문자열에서 JSON 본문을 최대한 복구해 파싱한다.

    로컬 모델은 코드펜스나 앞뒤 설명 문장을 붙이는 경우가 잦아,
    순수 ``json.loads`` 만으로는 실패율이 높다.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start_candidates = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
        if not start_candidates:
            raise LLMGenerationError("LLM 응답에서 JSON을 찾을 수 없습니다.")
        start = min(start_candidates)
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end < start:
            raise LLMGenerationError("LLM 응답 JSON이 완전하지 않습니다.")
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMGenerationError("LLM 응답 JSON을 해석할 수 없습니다.") from exc


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def validate_candidates(
    payload: Any,
    *,
    references: list[str] | None = None,
    minimum_count: int = 1,
) -> list[dict]:
    """LLM 응답을 검증해 사용 가능한 후보만 남긴다.

    길이 이상치 · 중복 · 참고 댓글 복사본을 제거하고, 허용되지 않은 유형은
    ``general`` 로 강등한다.
    """
    raw_candidates = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(raw_candidates, list):
        raise LLMGenerationError("LLM 응답에 candidates 배열이 없습니다.")

    reference_norms = [_normalize(item) for item in (references or []) if item.strip()]
    results: list[dict] = []
    seen: set[str] = set()

    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        comment = str(item.get("comment") or "").strip()
        comment_type = str(item.get("type") or "general").strip().lower()
        if comment_type not in ALLOWED_TYPES:
            comment_type = "general"
        if len(comment) < 5 or len(comment) > 200:
            continue
        normalized = _normalize(comment)
        if normalized in seen:
            continue
        if any(SequenceMatcher(None, normalized, reference).ratio() >= 0.92 for reference in reference_norms):
            continue
        seen.add(normalized)
        results.append({"type": comment_type, "comment": comment})

    if len(results) < minimum_count:
        raise LLMGenerationError(
            f"검증 후 사용할 수 있는 LLM 후보가 부족합니다 ({len(results)}/{minimum_count})."
        )
    return results
