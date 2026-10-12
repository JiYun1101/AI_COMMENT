"""Graph smoke tests without external API keys."""
import pytest
from casts.comment_writer.graph import comment_writer_graph
from casts.comment_writer.modules import nodes


def test_graph_invokes_context_and_ranker(monkeypatch):
    fake_context = {
        "video_id": "abcdefghijk",
        "post_text": "테스트 영상 정보",
        "generation_context": {"source": {"type": "youtube"}},
        "context_summary": {"primary_category": "Gaming"},
    }
    seen = {}
    def fake_context_fn(url, **kwargs):
        assert "youtu" in url
        return fake_context
    def fake_recommend(post_text, **kwargs):
        seen.update(kwargs)
        assert post_text == "테스트 영상 정보"
        return {"recommendations":[{"rank":1,"type":"general","comment":"좋은 영상이에요","predicted_score":80.0}], "trace":{"candidates":[]}}
    monkeypatch.setattr(nodes, "collect_video_context", fake_context_fn)
    monkeypatch.setattr(nodes, "recommend_comments_with_meta", fake_recommend)
    output = comment_writer_graph.invoke({"video_url":"https://youtu.be/abcdefghijk","top_k":1})
    assert len(output["recommendations"]) == 1
    assert output["context_summary"]["primary_category"] == "Gaming"
    assert seen["top_k"] == 1


def test_graph_rejects_empty_url():
    with pytest.raises(ValueError, match="video_url"):
        comment_writer_graph.invoke({"video_url":""})


def test_graph_forwards_request_scoped_keys_without_returning_them(monkeypatch):
    seen = {}
    def fake_context(url, **kwargs):
        seen["youtube_key"] = kwargs.get("youtube_api_key")
        return {
            "video_id": "abcdefghijk",
            "post_text": "sample",
            "generation_context": {},
            "context_summary": {"primary_category": "Software"},
        }
    class FakeOpenAIClient:
        def __init__(self, *, api_key, model):
            seen["openai_key"], seen["openai_model"] = api_key, model
    def fake_ranker(text, **kwargs):
        assert isinstance(kwargs["generation_client"], FakeOpenAIClient)
        return {"recommendations": [{"comment": "테스트", "rank": 1}], "trace": {"candidates": []}}
    monkeypatch.setattr(nodes, "collect_video_context", fake_context)
    monkeypatch.setattr(nodes, "OpenAIResponsesClient", FakeOpenAIClient)
    monkeypatch.setattr(nodes, "recommend_comments_with_meta", fake_ranker)
    out = comment_writer_graph.invoke({
        "video_url": "https://youtu.be/abcdefghijk",
        "top_k": 1,
        "youtube_api_key": "youtube-test-key",
        "openai_api_key": "openai-test-key",
        "openai_model": "test-model",
    })
    assert seen == {
        "youtube_key": "youtube-test-key",
        "openai_key": "openai-test-key",
        "openai_model": "test-model",
    }
    assert "openai-test-key" not in str(out)
    assert "youtube-test-key" not in str(out)
