from __future__ import annotations

import time
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.security import create_paired_session

client = TestClient(app)


def test_pairing_requires_server_provisioned_invitation(monkeypatch):
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("API_PAIRING_TOKEN", raising=False)
    monkeypatch.delenv("API_PAIRING_EXPIRES_AT", raising=False)
    res = client.post("/auth/connect", json={"pairing_code": "x" * 48})
    assert res.status_code == 503
    assert "access_token" not in res.text


def test_pairing_rejects_bad_or_expired_invitation(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "long-test-only-master-key")
    monkeypatch.setenv("API_PAIRING_TOKEN", "p" * 48)
    monkeypatch.setenv("API_PAIRING_EXPIRES_AT", str(int(time.time()) + 90))
    assert client.post("/auth/connect", json={"pairing_code": "x" * 48}).status_code == 401
    monkeypatch.setenv("API_PAIRING_EXPIRES_AT", str(int(time.time()) - 1))
    assert client.post("/auth/connect", json={"pairing_code": "p" * 48}).status_code == 503


def test_pairing_accepts_private_invitation_then_protects_requests(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "long-test-only-master-key")
    monkeypatch.setenv("API_PAIRING_TOKEN", "p" * 48)
    monkeypatch.setenv("API_PAIRING_EXPIRES_AT", str(int(time.time()) + 90))
    assert client.get("/auth/session").status_code == 401

    res = client.post("/auth/connect", json={"pairing_code": "p" * 48})
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-store"
    access = res.json()["access_token"]
    assert access.startswith("acs1.")
    assert "long-test-only-master-key" not in res.text
    assert client.get("/auth/session", headers={"X-API-Key": access}).json() == {"connected": True}
    assert client.get("/my-comments", headers={"X-API-Key": access}).status_code == 200
    assert client.get("/auth/session", headers={"X-API-Key": "long-test-only-master-key"}).status_code == 200

    damaged = access[:-1] + ("Z" if access[-1] != "Z" else "Y")
    assert client.get("/auth/session", headers={"X-API-Key": damaged}).status_code == 401


def test_rotated_master_secret_and_expired_sessions_stop_working(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "long-test-only-master-key")
    monkeypatch.setenv("API_PAIRING_TOKEN", "p" * 48)
    monkeypatch.setenv("API_PAIRING_EXPIRES_AT", str(int(time.time()) + 90))
    session = create_paired_session("p" * 48)
    monkeypatch.setenv("API_AUTH_TOKEN", "rotated-master-secret")
    assert client.get("/auth/session", headers={"X-API-Key": session["access_token"]}).status_code == 401
    monkeypatch.setenv("API_AUTH_TOKEN", "long-test-only-master-key")
    monkeypatch.setattr("src.api.security.time.time", lambda: session["expires_at"] + 1)
    assert client.get("/auth/session", headers={"X-API-Key": session["access_token"]}).status_code == 401
