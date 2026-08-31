import json

from src.llm.gemini_client import GeminiInteractionsClient


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


def _gemini_response():
    return {
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "candidates": [
                                    {"type": "casual", "comment": "영상 흐름이 자연스러워서 끝까지 보게 되네요."},
                                    {"type": "question", "comment": "다음 영상에서는 이 부분을 더 자세히 다뤄주실까요?"},
                                ]
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
            }
        ],
    }


def test_gemini_interactions_client_uses_generic_llm_configuration():
    session = FakeSession(FakeResponse(_gemini_response()))
    client = GeminiInteractionsClient(
        api_key="gemini-key",
        model="gemini-3.7-flash",
        base_url="https://example.test/v1beta2",
        thinking_level="medium",
        session=session,
    )

    result = client.generate({"historical_comments": {"reference_examples": []}}, candidate_count=4)

    assert len(result) == 2
    url, headers, payload, _ = session.calls[0]
    assert url == "https://example.test/v1beta2/interactions"
    assert headers["x-goog-api-key"] == "gemini-key"
    assert payload["model"] == "gemini-3.7-flash"
    assert payload["generation_config"]["thinking_level"] == "medium"
    assert payload["response_format"][0]["mime_type"] == "application/json"
