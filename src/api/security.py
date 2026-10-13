from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import time

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



PAIRED_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60


def pairing_available() -> bool:
    """Only server-configured, time-limited invitations can create sessions."""
    if not (os.getenv("API_AUTH_TOKEN") or "").strip():
        return False
    if not (os.getenv("API_PAIRING_TOKEN") or "").strip():
        return False
    try:
        expires_at = int(os.getenv("API_PAIRING_EXPIRES_AT") or "0")
    except ValueError:
        return False
    return expires_at > int(time.time())


def create_paired_session(pairing_code: str) -> dict:
    """Never return the server master secret; mint a 30-day signed session."""
    if not pairing_available():
        raise HTTPException(status_code=503, detail="서버 연결 초대가 준비되지 않았거나 만료되었습니다.")
    expected = (os.getenv("API_PAIRING_TOKEN") or "").strip()
    if not secrets.compare_digest(pairing_code.strip(), expected):
        logger.warning("api.auth.pairing_rejected")
        raise HTTPException(status_code=401, detail="서버 연결 코드가 유효하지 않습니다.")

    expiry = int(time.time()) + PAIRED_SESSION_TTL_SECONDS
    nonce = secrets.token_urlsafe(18)
    payload = f"acs1.{expiry}.{nonce}"
    key = (os.getenv("API_AUTH_TOKEN") or "").encode("utf-8")
    signature = base64.urlsafe_b64encode(
        hmac.new(key, payload.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return {"access_token": f"{payload}.{signature}", "expires_at": expiry}


def _valid_paired_session(value: str, key: str) -> bool:
    pieces = value.split(".")
    if len(pieces) != 4 or pieces[0] != "acs1":
        return False
    try:
        expiry = int(pieces[1])
    except ValueError:
        return False
    now = int(time.time())
    if not (now < expiry <= now + PAIRED_SESSION_TTL_SECONDS):
        return False
    if not (12 <= len(pieces[2]) <= 64 and 32 <= len(pieces[3]) <= 64):
        return False
    message = ".".join(pieces[:3])
    expected = base64.urlsafe_b64encode(
        hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return secrets.compare_digest(pieces[3], expected)


def auth_status() -> dict:
    """현재 보호 방식. readiness UI가 원격 노출 여부를 표시할 수 있게 노출한다."""
    configured = bool((os.getenv("API_AUTH_TOKEN") or "").strip())
    return {
        "mode": "api_key" if configured else "loopback_only",
        "header": API_KEY_HEADER,
        "pairing_available": pairing_available(),
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
        if not (secrets.compare_digest(provided, token) or _valid_paired_session(provided, token)):
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
