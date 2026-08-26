import pytest

from src.recommender.candidate_generator import generate_candidates


class FakeClient:
    def __init__(self):
        self.calls = []

    def generate(self, context, *, candidate_count):
        self.calls.append((context, candidate_count))
        types = ["insight", "empathy", "question", "casual", "general"]
        return [
            {
                "type": types[index % len(types)],
                "comment": f"영상 맥락을 반영한 자연스러운 테스트 댓글 {index + 1}입니다.",
            }
            for index in range(candidate_count)
        ]


def test_candidates_are_generated_from_context_through_llm_boundary():
    context = {
        "primary_category": "Science & Technology",
        "content": {"topics": ["ai", "software"]},
        "historical_comments": {"reference_examples": []},
    }
    client = FakeClient()
    candidates = generate_candidates(context, minimum_count=10, client=client)

    assert len(candidates) == 20
    assert client.calls[0][0] is context
    assert client.calls[0][1] == 20
    assert {item["type"] for item in candidates} >= {"insight", "empathy", "question", "casual", "general"}


def test_candidate_pool_scales_and_is_capped():
    client = FakeClient()
    context = {"historical_comments": {"reference_examples": []}}
    assert len(generate_candidates(context, minimum_count=3, client=client)) == 20
    assert len(generate_candidates(context, minimum_count=20, client=client)) == 30


def test_invalid_minimum_count_is_rejected():
    with pytest.raises(ValueError):
        generate_candidates({}, minimum_count=0, client=FakeClient())
