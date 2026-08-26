import pytest

from src.llm.openai_client import (
    LLMGenerationError,
    LLMNotReadyError,
    OpenAIResponsesClient,
    validate_candidates,
)


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, headers, json, timeout):
        self.calls.append((url, headers, json, timeout))
        return self.response


def test_validate_candidates_dedupes_and_rejects_reference_copy():
    payload = {
        "candidates": [
            {"type": "insight", "comment": "이 영상은 AI 설명 흐름이 특히 좋네요."},
            {"type": "insight", "comment": "이 영상은 AI 설명 흐름이 특히 좋네요."},
            {"type": "unknown", "comment": "다음 주제도 궁금해서 계속 보고 싶어요."},
            {"type": "casual", "comment": "참고 댓글 그대로 복사"},
        ]
    }
    result = validate_candidates(payload, references=["참고 댓글 그대로 복사"], minimum_count=2)
    assert len(result) == 2
    assert result[1]["type"] == "general"


def test_openai_client_parses_responses_api_output():
    response_payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"candidates":[{"type":"question","comment":"이 부분을 실제 업무에 적용하면 어떻게 달라질지 궁금해요."},{"type":"insight","comment":"핵심을 사례 중심으로 풀어서 이해하기 좋았습니다."}]}'
                    }
                ],
            }
        ]
    }
    session = FakeSession(FakeResponse(response_payload))
    client = OpenAIResponsesClient(api_key="test-key", model="test-model", base_url="https://example.test/v1", session=session)
    result = client.generate({"historical_comments": {"reference_examples": []}}, candidate_count=4)
    assert len(result) == 2
    assert session.calls[0][0] == "https://example.test/v1/responses"
    assert session.calls[0][2]["model"] == "test-model"


def test_openai_client_requires_explicit_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client = OpenAIResponsesClient(api_key=None, model=None)
    with pytest.raises(LLMNotReadyError):
        client.generate({}, candidate_count=5)


def test_invalid_response_is_generation_error():
    session = FakeSession(FakeResponse({"output": []}))
    client = OpenAIResponsesClient(api_key="key", model="model", session=session)
    with pytest.raises(LLMGenerationError):
        client.generate({}, candidate_count=5)
