from unittest.mock import MagicMock, patch

import pytest

from src.llm.openai_client import OpenAIResponsesClient
from src.viewer.auto_replies import (
    candidate_targets, suggest_replies, verified_parent_comment,
)
from src.youtube.comments import YouTubeCommentPublishError, publish_youtube_reply


def _thread(cid, text, *, author="another", reply_author=None):
    return {
        "id": cid, "author": "user", "author_channel_id": author,
        "text": text, "can_reply": True, "like_count": 2,
        "replies": ([{"author_channel_id": reply_author}] if reply_author else []),
    }


def test_target_filter_skips_self_and_existing_reply():
    threads = [
        _thread("comment001", "이 영상에서 말한 내용이 어떻게 작동하는지 궁금해요?"),
        _thread("comment002", "제가 작성한 질문인데 답변이 필요해요?", author="mine"),
        _thread("comment003", "여기서 사용한 도구가 뭔지 궁금해요?", reply_author="mine"),
        _thread("comment004", "짧음"),
    ]
    rows = candidate_targets(threads, viewer_channel_id="mine")
    assert [row["parent_id"] for row in rows] == ["comment001"]
    assert rows[0]["category"] == "question"


def test_context_verifies_youtube_video_binding():
    body = {"items": [{"id": "comment001", "snippet": {
        "videoId": "abcdefghijk", "canReply": True,
        "topLevelComment": {"snippet": {
            "textOriginal": "이 영상에서 설명한 흐름이 정말 궁금합니다.",
            "authorChannelId": {"value": "another"},
        }},
    }}]}
    with patch("src.viewer.auto_replies._authorized_json", return_value=body):
        result = verified_parent_comment(parent_id="comment001", video_id="abcdefghijk")
        assert result["author_channel_id"] == "another"
        with pytest.raises(YouTubeCommentPublishError) as exc:
            verified_parent_comment(parent_id="comment001", video_id="zzzzzzzzzzz")
        assert exc.value.status_code == 422


def test_ai_drafts_grounded_and_filtered():
    session = MagicMock()
    session.post.return_value.status_code = 200
    session.post.return_value.json.return_value = {
        "output_text": '{"drafts":["그 부분은 영상 설명에도 정확히 나오지 않아서 궁금하네요!","맞아요, 그 과정이 어떻게 되는지 저도 궁금해요.","https://spam.com 구매해요"]}',
    }
    client = OpenAIResponsesClient(api_key="test", model="test-model", session=session)
    result = suggest_replies(
        comment="과정이 어떻게 이뤄지는지 궁금합니다.",
        video_title="소개 영상", video_description="자세한 과정은 공개하지 않았습니다.",
        client=client,
    )
    assert len(result) == 2
    request_body = session.post.call_args.kwargs["json"]
    assert "original_comment" in request_body["input"]
    assert "YouTube comment REPLIES" in request_body["instructions"]


def test_auto_reply_rejects_existing_youtube_reply():
    mock_http = MagicMock()
    with (patch("src.youtube.comments._authorized_json") as fetch,
          patch("src.youtube.comments._authorized_request") as post):
        fetch.side_effect = [
            {"items": [{"id": "my-channel"}]},
            {"items": [{"snippet": {"videoId": "abcdefghijk", "channelId": "video-owner"}}]},
            {"items": [{"snippet": {"authorChannelId": {"value": "my-channel"}}}]},
        ]
        with pytest.raises(YouTubeCommentPublishError) as exc:
            publish_youtube_reply(
                parent_id="comment001", text="답글 테스트입니다.",
                require_video_owner=False, prevent_duplicate=True, session=mock_http,
            )
        assert exc.value.status_code == 409
        post.assert_not_called()


def test_auto_reply_post_checks_before_inserting():
    mock_http = MagicMock()
    result = MagicMock()
    result.status_code = 200
    result.json.return_value = {"id": "reply001"}
    with (patch("src.youtube.comments._authorized_json") as fetch,
          patch("src.youtube.comments._authorized_request", return_value=result) as post):
        fetch.side_effect = [
            {"items": [{"id": "my-channel"}]},
            {"items": [{"snippet": {"videoId": "abcdefghijk", "channelId": "other-channel"}}]},
            {"items": []},
        ]
        payload = publish_youtube_reply(
            parent_id="comment001", text="답글 테스트입니다.",
            require_video_owner=False, prevent_duplicate=True, session=mock_http,
        )
        assert payload["posted"]
        assert post.call_args.kwargs["json"]["snippet"]["parentId"] == "comment001"
