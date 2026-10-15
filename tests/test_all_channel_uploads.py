from unittest.mock import patch
from src.youtube.video_performance import fetch_my_videos


def test_full_upload_pagination_without_default_limit():
    video_ids = [f"x{n:010d}" for n in range(110)]
    first = {"items": [{"contentDetails": {"videoId": x}} for x in video_ids[:50]], "nextPageToken": "page2"}
    second = {"items": [{"contentDetails": {"videoId": x}} for x in video_ids[50:100]], "nextPageToken": "page3"}
    third = {"items": [{"contentDetails": {"videoId": x}} for x in video_ids[100:]]}
    def fake_authorized(http, url, params, **kwargs):
        if url.endswith("/playlistItems"):
            return {"page3": third, "page2": second}.get(params.get("pageToken"), first)
        if url.endswith("/videos"):
            return {"items": [{"id": x, "snippet": {"channelId": "owner", "title": x},
                               "statistics": {"viewCount": "10"}, "status": {"privacyStatus": "public"}}
                              for x in params["id"].split(",")]}
        raise AssertionError(url)
    with patch("src.youtube.video_performance._channel", return_value={
        "channel_id": "owner", "channel_title": "Channel", "uploads_playlist": "uploads",
    }), patch("src.youtube.video_performance._authorized_json", side_effect=fake_authorized):
        result = fetch_my_videos()
    assert len(result["videos"]) == 110
    assert not result["limit_reached"]
    assert result["videos"][0]["video_id"] == video_ids[0]
    assert result["videos"][-1]["video_id"] == video_ids[-1]
