import json
import time

import pytest

from src.creator.inbox import build_inbox, classify_inbox_comment
from src.creator.reply_drafts import draft_replies
from src.youtube.comments import YouTubeCommentPublishError, publish_youtube_reply
from src.youtube.engagement import fetch_comment_metrics, fetch_video_comment_threads

OWNER = "UC-owner"


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected {method}: {url}")
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        return self._next("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._next("POST", url, kwargs)

    def request(self, method, url, **kwargs):
        return self._next(method, url, kwargs)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("이 카메라 어디서 사셨어요?", "question"),
        ("편집 프로그램은 뭐예요", "question"),
        ("소리가 작아서 잘 안 들려요", "complaint"),
        ("뒷광고 아닌가요 신고합니다", "risk"),
        ("구독 부탁드려요 제 채널도 와주세요", "risk"),
        ("오늘 영상 정말 유익했어요 감사합니다", "praise"),
        ("첫 번째", "other"),
    ],
)
def test_classify_inbox_comment(text, expected):
    assert classify_inbox_comment(text)[0] == expected


def _thread(thread_id, text, *, likes=0, author=None, replies=()):
    return {
        "id": thread_id,
        "author": "viewer",
        "author_channel_id": author or f"UC-{thread_id}",
        "text": text,
        "like_count": likes,
        "reply_count": len(replies),
        "published_at": "2026-10-01T00:00:00Z",
        "can_reply": True,
        "replies": [{"author_channel_id": channel, "text": "답글"} for channel in replies],
    }


def test_build_inbox_puts_unanswered_questions_first_and_skips_own_comments():
    inbox = build_inbox(
        [
            _thread("praise", "최고예요 응원합니다", likes=200),
            _thread("answered", "렌즈는 뭐 쓰세요?", likes=50, replies=[OWNER]),
            _thread("open", "렌즈는 뭐 쓰세요?", likes=3),
            _thread("pinned", "고정: 영상에 쓴 장비 목록입니다", author=OWNER),
        ],
        channel_id=OWNER,
    )

    ids = [item["id"] for item in inbox["items"]]
    assert ids[0] == "open"
    assert "pinned" not in ids
    answered = next(item for item in inbox["items"] if item["id"] == "answered")
    assert answered["creator_replied"] is True and answered["needs_reply"] is False
    assert inbox["summary"] == {
        "total": 3,
        "needs_reply": 1,
        "creator_replied": 1,
        "own_comments": 1,
        "by_category": {"question": 2, "complaint": 0, "risk": 0, "praise": 1, "other": 0},
    }


def test_template_drafts_are_returned_without_llm():
    result = draft_replies(comment="렌즈는 뭐 쓰세요?", category="question")
    assert result["source"] == "template"
    assert len(result["drafts"]) == 3


def test_llm_drafts_drop_unsafe_lines_and_fall_back_when_empty():
    class FakeClient:
        api_key = "k"
        model = "m"
        base_url = "https://example.test/v1"
        timeout = 5

        def __init__(self, drafts):
            self.session = FakeSession(
                [FakeResponse({"output_text": json.dumps({"drafts": drafts}, ensure_ascii=False)})]
            )

        def _ensure_ready(self):
            return None

    ok = draft_replies(
        comment="렌즈는 뭐 쓰세요?",
        category="question",
        client=FakeClient(["50mm 단렌즈를 썼어요!", "구독 부탁드려요"]),
    )
    assert ok == {"source": "llm", "drafts": ["50mm 단렌즈를 썼어요!"]}

    fallback = draft_replies(comment="렌즈는?", category="question", client=FakeClient(["구독 부탁드려요"]))
    assert fallback["source"] == "template"


def test_fetch_comment_metrics_batches_and_omits_missing_ids():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "items": [
                        {
                            "id": "c1",
                            "snippet": {"totalReplyCount": 2, "topLevelComment": {"snippet": {"likeCount": 7}}},
                        }
                    ]
                }
            )
        ]
    )
    metrics = fetch_comment_metrics(["c1", "c2"], api_key="key", session=session)
    assert metrics == {"c1": {"like_count": 7, "reply_count": 2}}
    assert session.calls[0][2]["params"]["id"] == "c1,c2"


def test_fetch_video_comment_threads_follows_pages_and_reports_disabled_comments():
    def page(thread_id, token=None):
        body = {
            "items": [
                {
                    "id": thread_id,
                    "snippet": {
                        "totalReplyCount": 1,
                        "canReply": True,
                        "topLevelComment": {
                            "snippet": {
                                "authorDisplayName": "viewer",
                                "authorChannelId": {"value": "UC-viewer"},
                                "textOriginal": "질문 있어요?",
                                "likeCount": 4,
                            }
                        },
                    },
                    "replies": {"comments": [{"snippet": {"authorChannelId": {"value": OWNER}, "textOriginal": "네"}}]},
                }
            ]
        }
        if token:
            body["nextPageToken"] = token
        return FakeResponse(body)

    session = FakeSession([page("t1", "next"), page("t2")])
    threads = fetch_video_comment_threads("dQw4w9WgXcQ", api_key="key", session=session)
    assert [thread["id"] for thread in threads] == ["t1", "t2"]
    assert threads[0]["replies"][0]["author_channel_id"] == OWNER
    assert session.calls[1][2]["params"]["pageToken"] == "next"

    from src.youtube.context import YouTubeLookupError

    disabled = FakeSession(
        [FakeResponse({"error": {"errors": [{"reason": "commentsDisabled"}]}}, status_code=403)]
    )
    with pytest.raises(YouTubeLookupError, match="사용 중지"):
        fetch_video_comment_threads("dQw4w9WgXcQ", api_key="key", session=disabled)


@pytest.fixture
def authorized_oauth(tmp_path, monkeypatch):
    token_path = tmp_path / "youtube-token.json"
    token_path.write_text(
        json.dumps({"access_token": "access", "refresh_token": "refresh", "expires_at": time.time() + 3600}),
        encoding="utf-8",
    )
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("YOUTUBE_OAUTH_TOKEN_PATH", str(token_path))


def test_reply_is_posted_only_on_videos_owned_by_connected_channel(authorized_oauth):
    session = FakeSession(
        [
            FakeResponse({"items": [{"id": OWNER}]}),
            FakeResponse({"items": [{"snippet": {"channelId": OWNER, "videoId": "dQw4w9WgXcQ"}}]}),
            FakeResponse({"id": "reply-1"}),
        ]
    )
    result = publish_youtube_reply(parent_id="thread-1", text="확인해 볼게요!", session=session)

    assert result["reply_id"] == "reply-1"
    assert result["comment_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&lc=reply-1"
    method, _, kwargs = session.calls[2]
    assert method == "POST"
    assert kwargs["json"] == {"snippet": {"parentId": "thread-1", "textOriginal": "확인해 볼게요!"}}
    assert kwargs["headers"]["Authorization"] == "Bearer access"


def test_reply_on_someone_elses_video_is_refused(authorized_oauth):
    session = FakeSession(
        [
            FakeResponse({"items": [{"id": OWNER}]}),
            FakeResponse({"items": [{"snippet": {"channelId": "UC-other", "videoId": "dQw4w9WgXcQ"}}]}),
        ]
    )
    with pytest.raises(YouTubeCommentPublishError) as exc_info:
        publish_youtube_reply(parent_id="thread-1", text="확인해 볼게요!", session=session)
    assert exc_info.value.status_code == 403
    assert len(session.calls) == 2
