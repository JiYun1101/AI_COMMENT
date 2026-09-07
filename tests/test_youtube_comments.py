import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from src.youtube.comments import (
    YOUTUBE_COMMENT_THREADS_URL,
    YouTubeOAuthNotAuthorizedError,
    complete_youtube_oauth,
    create_youtube_authorization_url,
    publish_youtube_comment,
    youtube_oauth_status,
)


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

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected POST: {url}")
        return self.responses.pop(0)


@pytest.fixture
def oauth_env(tmp_path, monkeypatch):
    token_path = tmp_path / "youtube-token.json"
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("YOUTUBE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/youtube/oauth/callback")
    monkeypatch.setenv("YOUTUBE_OAUTH_TOKEN_PATH", str(token_path))
    return token_path


def _state_from_auth_url(url: str) -> str:
    params = parse_qs(urlparse(url).query)
    return params["state"][0]


def test_authorization_url_uses_youtube_scope_and_pkce(oauth_env):
    url = create_youtube_authorization_url()
    params = parse_qs(urlparse(url).query)

    assert params["client_id"] == ["client-id"]
    assert params["scope"] == ["https://www.googleapis.com/auth/youtube.force-ssl"]
    assert params["access_type"] == ["offline"]
    assert params["prompt"] == ["consent"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"][0]


def test_oauth_callback_persists_token_and_comment_publish_uses_it(oauth_env):
    auth_url = create_youtube_authorization_url()
    state = _state_from_auth_url(auth_url)
    session = FakeSession(
        [
            FakeResponse(
                {
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                    "scope": "https://www.googleapis.com/auth/youtube.force-ssl",
                    "token_type": "Bearer",
                }
            ),
            FakeResponse(
                {
                    "id": "thread-1",
                    "snippet": {
                        "topLevelComment": {
                            "id": "comment-1",
                            "snippet": {"textOriginal": "자동 게시 테스트 댓글"},
                        }
                    },
                }
            ),
        ]
    )

    status = complete_youtube_oauth("authorization-code", state, session=session)
    assert status["authorized"] is True
    assert oauth_env.exists()

    result = publish_youtube_comment(
        video_id="dQw4w9WgXcQ",
        channel_id="UC-test-channel",
        comment="자동 게시 테스트 댓글",
        session=session,
    )

    assert result["posted"] is True
    assert result["comment_id"] == "comment-1"
    assert "lc=comment-1" in result["comment_url"]
    post_url, kwargs = session.calls[1]
    assert post_url == YOUTUBE_COMMENT_THREADS_URL
    assert kwargs["params"] == {"part": "snippet"}
    assert kwargs["headers"]["Authorization"] == "Bearer access-1"
    assert kwargs["json"]["snippet"]["channelId"] == "UC-test-channel"
    assert kwargs["json"]["snippet"]["videoId"] == "dQw4w9WgXcQ"
    assert (
        kwargs["json"]["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
        == "자동 게시 테스트 댓글"
    )


def test_expired_access_token_is_refreshed_before_publish(oauth_env):
    Path(oauth_env).write_text(
        json.dumps(
            {
                "access_token": "expired",
                "refresh_token": "refresh-1",
                "expires_at": time.time() - 10,
            }
        ),
        encoding="utf-8",
    )
    session = FakeSession(
        [
            FakeResponse({"access_token": "access-2", "expires_in": 3600, "token_type": "Bearer"}),
            FakeResponse(
                {
                    "id": "thread-2",
                    "snippet": {"topLevelComment": {"id": "comment-2"}},
                }
            ),
        ]
    )

    result = publish_youtube_comment(
        video_id="dQw4w9WgXcQ",
        channel_id="UC-test-channel",
        comment="갱신 후 게시",
        session=session,
    )

    assert result["comment_id"] == "comment-2"
    assert session.calls[0][0] == "https://oauth2.googleapis.com/token"
    assert session.calls[0][1]["data"]["grant_type"] == "refresh_token"
    assert session.calls[1][1]["headers"]["Authorization"] == "Bearer access-2"


def test_publish_requires_connected_account(oauth_env):
    with pytest.raises(YouTubeOAuthNotAuthorizedError):
        publish_youtube_comment(
            video_id="dQw4w9WgXcQ",
            channel_id="UC-test-channel",
            comment="게시 불가",
            session=FakeSession([]),
        )

    assert youtube_oauth_status()["authorized"] is False
