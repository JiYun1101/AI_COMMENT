"""Regression tests for the safe, read-only presentation preflight."""
from unittest.mock import patch

import pytest

from scripts.smoke_presentation import Check, evaluate_health, fetch_readonly, main, safe_base


def healthy(*, youtube=True, persistent=False):
    return {
        "model": {"ready": True},
        "llm": {"ready": True},
        "youtube": {"configured": youtube, "demo": {"ready": False}},
        "storage": {"ready": True, "persistent": persistent},
    }


def test_health_explicitly_warns_about_ephemeral_storage():
    checks = evaluate_health(healthy(), "youtube")
    assert any(c.name == "영구 보존" and c.level == "WARN" for c in checks)
    assert all(c.level != "BLOCK" for c in checks)


def test_missing_youtube_blocks_url_demo_but_not_manual():
    assert any(c.name == "YouTube 영상 정보" and c.level == "BLOCK"
               for c in evaluate_health(healthy(youtube=False), "youtube"))
    assert any(c.name == "YouTube 영상 정보" and c.level == "WARN"
               for c in evaluate_health(healthy(youtube=False), "manual"))


def test_model_and_llm_readiness_are_required():
    data = healthy(persistent=True)
    data["model"] = {"ready": False}
    data["llm"] = {"ready": False}
    checks = evaluate_health(data, "manual")
    assert {c.name for c in checks if c.level == "BLOCK"} == {"반응 예측 Ranker", "LLM 댓글 생성"}


def test_malformed_health_is_not_reported_as_ready():
    assert evaluate_health([], "manual") == [
        Check("BLOCK", "API /health", "정상적인 JSON 응답을 받지 못했습니다.")
    ]


def test_credentials_never_embedded_in_plain_http_remote_urls():
    with pytest.raises(ValueError):
        safe_base("http://example.com")
    with pytest.raises(ValueError):
        safe_base("https://user:pass@example.com")
    with pytest.raises(ValueError):
        safe_base("https://example.com/?token=secret")
    assert safe_base("http://localhost:8000/") == "http://localhost:8000"


def test_readonly_requests_do_not_mutate_and_token_is_optional():
    class Response:
        status = 200
        headers = {"Content-Type": "application/json"}
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self, size):
            return b'{"status":"ok"}'

    with patch("scripts.smoke_presentation.urlopen", return_value=Response()) as mocked:
        status, body = fetch_readonly("https://example.com/health", 5, token="test-token")
        assert status == 200 and body["status"] == "ok"
        request = mocked.call_args.args[0]
        assert request.get_method() == "GET"
        assert request.get_header("X-api-key") == "test-token"


def test_cli_returns_nonzero_for_readiness_blockers(capsys):
    with patch("scripts.smoke_presentation.run_check",
               return_value=[Check("BLOCK", "LLM 댓글 생성", "미준비")]):
        assert main(["--mode", "manual", "--api", "http://localhost:8000",
                     "--web", "http://localhost:5173"]) == 2
    assert "[BLOCK]" in capsys.readouterr().out


def test_cli_returns_zero_for_warnings_only():
    with patch("scripts.smoke_presentation.run_check",
               return_value=[Check("WARN", "영구 보존", "미확인")]):
        assert main(["--mode", "manual", "--api", "http://localhost:8000",
                     "--web", "http://localhost:5173"]) == 0
