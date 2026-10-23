from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.api.main import restore_durable_comment_receipts


def test_restore_rejects_demo_mode():
    with pytest.raises(HTTPException) as exc:
        restore_durable_comment_receipts(account_mode="demo")
    assert exc.value.status_code == 403


def test_restore_requires_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(HTTPException) as exc:
        restore_durable_comment_receipts(account_mode="personal")
    assert exc.value.status_code == 503


def test_restore_never_imports_other_channel(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    with patch("src.api.main._verified_account_channel", return_value={"channel_id": "owner"}), \
         patch("src.storage.durable_receipts.list_receipts", return_value=[]):
        result = restore_durable_comment_receipts(account_mode="personal",
                                                   oauth_client_id=None,
                                                   oauth_client_secret=None,
                                                   oauth_redirect_uri=None)
    assert result == {"restored": 0, "failed": 0, "checked": 0}
