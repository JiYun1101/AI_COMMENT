#!/usr/bin/env python3
"""Read-only readiness check for the AI_COMMENT presentation.

No comments, recommendations, OAuth tokens or database rows are created.
Only health and optional authenticated GET endpoints are requested.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_WEB = "https://ai-comment-web.onrender.com"
DEFAULT_API = "https://ai-comment-api-lite.onrender.com"


@dataclass(frozen=True)
class Check:
    level: str  # PASS | WARN | BLOCK
    name: str
    detail: str


def safe_base(url: str) -> str:
    """Accept HTTPS, or HTTP only for localhost development."""
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("주소에 계정 정보·쿼리·프래그먼트를 넣지 마세요.")
    if parsed.scheme == "https" and parsed.netloc:
        return url.rstrip("/")
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return url.rstrip("/")
    raise ValueError("HTTPS URL 또는 로컬 개발용 http://localhost URL만 허용합니다.")


def fetch_readonly(url: str, timeout: float, *, token: str | None = None) -> tuple[int, Any]:
    headers = {"Accept": "application/json, text/html"}
    if token:
        headers["X-API-Key"] = token
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(1024 * 1024)
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return response.status, json.loads(raw)
            return response.status, raw.decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, None
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        # Do not print raw exception text, which may contain URLs/credentials.
        raise ConnectionError(type(exc).__name__) from None


def evaluate_health(data: Any, mode: str) -> list[Check]:
    if not isinstance(data, dict):
        return [Check("BLOCK", "API /health", "정상적인 JSON 응답을 받지 못했습니다.")]
    result: list[Check] = []
    for key, label in (("model", "반응 예측 Ranker"), ("llm", "LLM 댓글 생성")):
        entry = data.get(key)
        ready = isinstance(entry, dict) and entry.get("ready") is True
        result.append(Check("PASS" if ready else "BLOCK", label, "준비됨" if ready else "미준비 · 서버 모델/환경변수 점검"))
    youtube = data.get("youtube")
    configured = isinstance(youtube, dict) and youtube.get("configured") is True
    result.append(Check(
        "PASS" if configured else ("BLOCK" if mode == "youtube" else "WARN"),
        "YouTube 영상 정보",
        "API 키 설정됨" if configured else "API 키 없음 · URL 기반 시연 불가 (직접 입력은 가능)",
    ))
    storage = data.get("storage")
    ready = isinstance(storage, dict) and storage.get("ready") is True
    result.append(Check("PASS" if ready else "BLOCK", "분석 저장소", "응답 정상" if ready else "저장소 미준비"))
    persistent = isinstance(storage, dict) and storage.get("persistent") is True
    result.append(Check(
        "PASS" if persistent else "WARN",
        "영구 보존",
        "영구 저장 확인" if persistent else "영구 보존 미확인 · 발표 전 재배포/서버 재시작 금지, 기존 데이터 백업",
    ))
    demo = youtube.get("demo") if isinstance(youtube, dict) else None
    if isinstance(demo, dict) and demo.get("ready") is not True:
        result.append(Check("WARN", "YouTube 데모 게시", "데모 채널 게시 준비 안 됨 · 실제 게시 시연 제외"))
    return result


def run_check(web: str, api: str, mode: str, timeout: float, token: str | None) -> list[Check]:
    items: list[Check] = []
    try:
        status, body = fetch_readonly(web + "/", timeout)
        items.append(Check(
            "PASS" if status == 200 and isinstance(body, str) and "<html" in body.lower() else "BLOCK",
            "프론트엔드 접속",
            f"HTTP {status}" if status != 200 else "HTML 진입점 확인" if isinstance(body, str) and "<html" in body.lower() else "HTML 응답 형식 이상",
        ))
    except ConnectionError:
        items.append(Check("BLOCK", "프론트엔드 접속", "접속 실패/시간 초과"))

    try:
        status, body = fetch_readonly(api + "/health", timeout)
        if status != 200:
            items.append(Check("BLOCK", "API /health", f"HTTP {status}"))
        else:
            items.extend(evaluate_health(body, mode))
    except ConnectionError:
        items.append(Check("BLOCK", "API /health", "접속 실패/시간 초과 · Render 콜드 스타트 여부 확인"))

    if token:
        for path, name in (
            ("/auth/session", "브라우저-서버 연결 토큰"),
            ("/model/data-progress", "모델 데이터 축적 API"),
        ):
            try:
                status, body = fetch_readonly(api + path, timeout, token=token)
                valid = status == 200 and isinstance(body, dict)
                items.append(Check(
                    "PASS" if valid else "BLOCK", name,
                    "인증된 JSON 조회 성공" if valid else f"HTTP {status} · 토큰/서버 설정 확인",
                ))
            except ConnectionError:
                items.append(Check("BLOCK", name, "접속 실패/시간 초과"))
    else:
        items.append(Check("WARN", "인증 필요한 모델 데이터 API", "서버 연결 토큰 미제공 · 이 기능의 라이브 시연은 별도 확인 필요"))
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI_COMMENT 발표 전 읽기 전용 서버 점검")
    parser.add_argument("--web", default=DEFAULT_WEB, help="프론트엔드 기본 URL")
    parser.add_argument("--api", default=DEFAULT_API, help="FastAPI 기본 URL")
    parser.add_argument("--mode", choices=("manual", "youtube"), default="youtube", help="발표 시연 방식")
    parser.add_argument("--timeout", type=float, default=45, help="각 요청 제한 시간(초)")
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 180:
        parser.error("--timeout은 1~180초 범위여야 합니다.")
    try:
        web, api = safe_base(args.web), safe_base(args.api)
    except ValueError as error:
        parser.error(str(error))
    token = os.environ.get("AI_COMMENT_SERVER_TOKEN", "").strip() or None
    checks = run_check(web, api, args.mode, args.timeout, token)
    print("AI_COMMENT 발표 사전 점검 (GET 요청 전용 · 댓글/추천 생성 및 게시 없음)")
    for check in checks:
        print(f"[{check.level:5}] {check.name}: {check.detail}")
    blocked = sum(check.level == "BLOCK" for check in checks)
    print(f"\n결과: {blocked}개 차단 항목, {sum(check.level == 'WARN' for check in checks)}개 주의 항목")
    return 2 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
