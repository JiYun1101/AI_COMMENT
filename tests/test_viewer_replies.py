from unittest.mock import MagicMock, patch
from src.youtube.comments import publish_youtube_reply


def test_viewer_reply_does_not_require_video_ownership():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "reply123"}
    with patch("src.youtube.comments._authorized_json") as read, \
         patch("src.youtube.comments._authorized_request", return_value=response) as post:
        read.side_effect = [
            {"items": [{"id": "viewer-channel"}]},
            {"items": [{"snippet": {"channelId": "different-owner", "videoId": "abcdefghijk"}}]},
        ]
        result = publish_youtube_reply(parent_id="parent123", text="hello",
                                       require_video_owner=False)
    assert result["posted"] is True
    assert result["video_id"] == "abcdefghijk"
    assert post.call_args.kwargs["json"]["snippet"]["parentId"] == "parent123"
