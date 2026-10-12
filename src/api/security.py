from __future__ import annotations

import ipaddress
import logging
import os
import secrets

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def auth_status() -> dict:
    """현재 보호 방식. readiness UI가 원격 노출 여부를 표시할 수 있게 노출한다."""
    configured = bool((os.getenv("API_AUTH_TOKEN") or "").strip())
    return {
        "mode": "api_key" if configured else "loopback_only",
        "header": API_KEY_HEADER,
    }


def require_trusted_client(request: Request) -> None:
    """연결된 YouTube 계정을 건드리는 엔드포인트를 보호한다.

    CORS는 브라우저에만 적용되므로 curl/스크립트를 막지 못한다. OAuth 토큰이
    서버에 저장돼 있는 이상, 서버에 도달할 수 있는 누구나 사용자 계정으로 댓글을
    게시할 수 있다는 뜻이다. 그래서 두 단계로 막는다.

    - ``API_AUTH_TOKEN``이 설정돼 있으면 ``X-API-Key`` 헤더가 일치해야 한다.
    - 설정돼 있지 않으면 loopback(localhost) 요청만 허용한다. 단일 사용자
      로컬 MVP는 설정 없이 그대로 동작하고, 서버를 외부에 노출하는 순간
      토큰을 설정하지 않으면 거부된다.
    """
    token = (os.getenv("API_AUTH_TOKEN") or "").strip()
    if token:
        provided = request.headers.get(API_KEY_HEADER, "")
        if not secrets.compare_digest(provided, token):
            logger.warning("api.auth.rejected path=%s reason=invalid_key", request.url.path)
            raise HTTPException(
                status_code=401,
                detail=f"유효한 API 키가 필요합니다. {API_KEY_HEADER} 헤더를 확인해주세요.",
            )
        return

    host = request.client.host if request.client else None
    if not _is_loopback(host):
        logger.warning(
            "api.auth.rejected path=%s reason=remote_without_token host=%s",
            request.url.path,
            host,
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "이 엔드포인트는 기본적으로 localhost에서만 사용할 수 있습니다. "
                "원격에서 사용하려면 API_AUTH_TOKEN을 설정하고 "
                f"{API_KEY_HEADER} 헤더로 전달해주세요."
            ),
        )
