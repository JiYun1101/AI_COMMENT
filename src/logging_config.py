from __future__ import annotations

import logging
import os

DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_configured = False


def configure_logging() -> None:
    """애플리케이션 로깅을 한 번만 설정한다.

    이벤트는 ``도메인.동작 key=value`` 형태로 남긴다(예:
    ``recommend.completed elapsed_ms=8123 provider=ollama_local``). grep과
    로그 수집기 양쪽에서 다루기 쉬운 최소한의 구조다.

    레벨은 ``LOG_LEVEL``로 조절한다(기본 INFO).
    """
    global _configured
    if _configured:
        return

    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)

    # uvicorn access log는 요청 단위 노이즈가 커서 애플리케이션 이벤트를 묻는다.
    logging.getLogger("uvicorn.access").setLevel(max(level, logging.WARNING))
    _configured = True
