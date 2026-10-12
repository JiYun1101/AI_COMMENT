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
