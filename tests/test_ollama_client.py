import json

from src.llm.ollama_client import OllamaChatClient


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


def _ollama_response():
    return {
        "model": "qwen3:8b",
        "message": {
            "role": "assistant",
            "content": json.dumps(
                {
                    "candidates": [
                        {"type": "casual", "comment": "영상 분위기가 편해서 끝까지 보게 되네요."},
                        {"type": "question", "comment": "다음 영상에서도 이 주제를 이어서 다뤄주실까요?"},
                    ]
                },
                ensure_ascii=False,
            ),
        },
        "done": True,
    }


def test_ollama_client_uses_local_chat_structured_output():
    session = FakeSession(FakeResponse(_ollama_response()))
    client = OllamaChatClient(
        model="qwen3:8b",
        base_url="http://localhost:11434",
        session=session,
    )

    result = client.generate({"historical_comments": {"reference_examples": []}}, candidate_count=4)

    assert len(result) == 2
    url, headers, payload, timeout = session.calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert headers["Content-Type"] == "application/json"
    assert payload["model"] == "qwen3:8b"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["format"]["type"] == "object"
    assert payload["format"]["properties"]["candidates"]["type"] == "array"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert timeout == 120.0
