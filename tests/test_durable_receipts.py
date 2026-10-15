from unittest.mock import MagicMock, patch

import pytest

from src.storage.durable_receipts import durable_enabled, list_receipts, persist_receipt


def test_without_database_does_not_connect(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert not durable_enabled()
    persist_receipt(comment_id="c", video_id="v", owner_channel_id="owner")
    assert list_receipts("owner") == []


def test_owner_required_before_connection(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://invalid")
    with pytest.raises(ValueError, match="verified YouTube channel"):
        persist_receipt(comment_id="c", video_id="v", owner_channel_id="")
    with pytest.raises(ValueError, match="Owner channel"):
        list_receipts("")


def test_insert_is_parameterized_and_owner_scoped(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    cursor = MagicMock()
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    with patch("psycopg.connect", return_value=connection) as connect:
        persist_receipt(comment_id="c", video_id="v", owner_channel_id="owner", predicted_score=3.2)
    connect.assert_called_once()
    sql, params = cursor.execute.call_args.args
    assert "ON CONFLICT" in sql
    assert params[0:3] == ("c", "owner", "v")
    assert params[4] == 3.2
