from __future__ import annotations

import json
import os
from typing import Any

import requests

from src.llm.base import (
    ALLOWED_TYPES,
    LLMGenerationError,
    LLMNotReadyError,
    extract_json,
    validate_candidates,
)
from src.llm.prompting import SYSTEM_INSTRUCTIONS, build_user_input

# 기존 import 경로(`from src.llm.openai_client import LLMGenerationError` 등)를
# 유지하기 위한 재노출. 실제 정의는 src/llm/base.py, src/llm/prompting.py 에 있다.
__all__ = [
    "ALLOWED_TYPES",
    "DEFAULT_BASE_URL",
    "LLMGenerationError",
    "LLMNotReadyError",
    "OpenAIResponsesClient",
    "SYSTEM_INSTRUCTIONS",
    "llm_readiness",
    "validate_candidates",
]

DEFAULT_BASE_URL = "https://api.openai.com/v1"


def llm_readiness() -> dict:
    api_key = bool(os.getenv("OPENAI_API_KEY"))
    model = (os.getenv("OPENAI_MODEL") or "").strip()
    return {
        "ready": api_key and bool(model),
        "provider": "openai_responses_api",
        "model": model or None,
        "missing": [
            name
            for name, present in (("OPENAI_API_KEY", api_key), ("OPENAI_MODEL", bool(model)))
            if not present
        ],
    }


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if content.get("type") in {"output_text", "text"} and isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


class OpenAIResponsesClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        session=None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = (model or os.getenv("OPENAI_MODEL") or "").strip()
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def _ensure_ready(self) -> None:
        missing = []
        if not self.api_key:
            missing.append("OPENAI_API_KEY")
        if not self.model:
            missing.append("OPENAI_MODEL")
        if missing:
            raise LLMNotReadyError(f"LLM 설정이 필요합니다: {', '.join(missing)}")

    def generate(
        self,
        context: dict,
        *,
        candidate_count: int,
        comment_type: str | None = None,
        feedback: str | None = None,
    ) -> list[dict]:
        self._ensure_ready()
        historical = context.get("historical_comments") or {}
        user_input = build_user_input(
            context,
            candidate_count=candidate_count,
            comment_type=comment_type,
            feedback=feedback,
        )
        payload = {
            "model": self.model,
            "instructions": SYSTEM_INSTRUCTIONS,
            "input": json.dumps(user_input, ensure_ascii=False),
            "max_output_tokens": 6000,
        }

        try:
            response = self.session.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LLMGenerationError("LLM API에 연결할 수 없습니다.") from exc

        if response.status_code < 200 or response.status_code >= 300:
            detail = (getattr(response, "text", "") or "")[:300]
            raise LLMGenerationError(f"LLM API 요청이 실패했습니다 ({response.status_code}). {detail}".strip())

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise LLMGenerationError("LLM API 응답을 JSON으로 해석할 수 없습니다.") from exc

        output_text = _extract_output_text(response_payload)
        if not output_text:
            raise LLMGenerationError("LLM API 응답에 생성 텍스트가 없습니다.")
        parsed = extract_json(output_text)
        return validate_candidates(
            parsed,
            references=list(historical.get("reference_examples") or []),
            minimum_count=max(1, candidate_count // 2),
        )
