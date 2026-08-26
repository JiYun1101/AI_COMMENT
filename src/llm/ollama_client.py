"""로컬 LLM(Ollama) 댓글 생성 클라이언트.

``OpenAIResponsesClient`` 와 같은 ``generate(context, *, candidate_count)``
인터페이스를 구현하므로 ``generate_candidates(..., client=...)`` 에 그대로
꽂아 쓸 수 있다.

로컬 모델 특성상 아래 두 가지를 기본값으로 둔다.

* ``format="json"`` 으로 구조화 출력을 강제한다. 그래도 깨질 수 있어
  ``extract_json`` 이 코드펜스·잡음을 걷어낸다.
* 유형 다양성이 한 응답 안에서 빨리 무너지므로, 호출자가 ``comment_type`` 을
  지정해 유형별로 나눠 호출할 수 있게 열어 둔다.
"""

from __future__ import annotations

import json
import os

import requests

from src.llm.base import LLMGenerationError, LLMNotReadyError, extract_json, validate_candidates
from src.llm.prompting import SYSTEM_INSTRUCTIONS, build_user_input

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TEMPERATURE = 0.9
DEFAULT_NUM_PREDICT = 1024
DEFAULT_TIMEOUT = 120.0


def _float_env(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def ollama_readiness() -> dict:
    model = (os.getenv("OLLAMA_MODEL") or "").strip()
    base_url = (os.getenv("OLLAMA_BASE_URL") or DEFAULT_BASE_URL).strip()
    return {
        "ready": bool(model),
        "provider": "ollama",
        "model": model or None,
        "base_url": base_url,
        "missing": [] if model else ["OLLAMA_MODEL"],
    }


class OllamaCommentClient:
    """Ollama ``/api/chat`` 엔드포인트를 사용하는 댓글 후보 생성기."""

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        session=None,
        timeout: float | None = None,
        temperature: float | None = None,
        num_predict: int | None = None,
    ) -> None:
        self.model = (model or os.getenv("OLLAMA_MODEL") or "").strip()
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout if timeout is not None else _float_env("OLLAMA_TIMEOUT", DEFAULT_TIMEOUT)
        self.temperature = (
            temperature if temperature is not None else _float_env("OLLAMA_TEMPERATURE", DEFAULT_TEMPERATURE)
        )
        self.num_predict = (
            num_predict if num_predict is not None else _int_env("OLLAMA_NUM_PREDICT", DEFAULT_NUM_PREDICT)
        )

    def _ensure_ready(self) -> None:
        if not self.model:
            raise LLMNotReadyError("LLM 설정이 필요합니다: OLLAMA_MODEL")

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
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LLMGenerationError(
                f"로컬 LLM 서버에 연결할 수 없습니다 ({self.base_url}). Ollama 가 실행 중인지 확인하세요."
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            detail = (getattr(response, "text", "") or "")[:300]
            raise LLMGenerationError(f"로컬 LLM 요청이 실패했습니다 ({response.status_code}). {detail}".strip())

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise LLMGenerationError("로컬 LLM 응답을 JSON으로 해석할 수 없습니다.") from exc

        message = response_payload.get("message") or {}
        output_text = str(message.get("content") or "").strip()
        if not output_text:
            raise LLMGenerationError("로컬 LLM 응답에 생성 텍스트가 없습니다.")

        parsed = extract_json(output_text)
        return validate_candidates(
            parsed,
            references=list(historical.get("reference_examples") or []),
            minimum_count=max(1, candidate_count // 2),
        )
