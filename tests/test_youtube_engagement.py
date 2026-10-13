from src.youtube.engagement import fetch_comment_metrics


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class FakeYouTube:
    def __init__(self):
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params))
        assert url.endswith("/comments"), "Metrics should use comments.list, not commentThreads.list(id)"
        if "id" in params:
            assert "maxResults" not in params
            return FakeResponse({"items": [
                {"id": "comment-a", "snippet": {"likeCount": 9}},
                {"id": "comment-b", "snippet": {"likeCount": 3, "parentId": "original"}},
            ]})
        if params.get("parentId") == "comment-a":
            return FakeResponse({"items": [{"id": "reply-1"}], "pageInfo": {"totalResults": 1}})
        raise AssertionError("Unexpected request")


def test_metrics_use_comment_ids_and_reply_list():
    session = FakeYouTube()
    metrics = fetch_comment_metrics(["comment-a", "comment-b"], api_key="test-key", session=session)
    assert metrics == {
        "comment-a": {"like_count": 9, "reply_count": 1},
        "comment-b": {"like_count": 3, "reply_count": 0},
    }
    assert len(session.calls) == 2
