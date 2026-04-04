"""Tests for the admin API."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from textgame_io.admin import add_admin_routes
from textgame_io.messages import NarrativeMessage, ServerMessage
from textgame_io.server import GameServer, GameSession


class DummyServer(GameServer):
    async def handle_connect(self, session: GameSession) -> list[ServerMessage]:
        return [NarrativeMessage(text="Hi")]

    async def handle_command(self, session: GameSession, text: str) -> list[ServerMessage]:
        return [NarrativeMessage(text=text)]


@pytest.fixture
def setup():
    server = DummyServer()
    app = server.as_asgi()
    add_admin_routes(app, server, admin_token="test-token")
    client = TestClient(app)
    return server, client


class TestAdminAuth:
    def test_no_token_rejected(self, setup) -> None:
        _, client = setup
        resp = client.get("/admin/sessions")
        assert resp.status_code == 401

    def test_wrong_token_rejected(self, setup) -> None:
        _, client = setup
        resp = client.get("/admin/sessions", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_correct_token_accepted(self, setup) -> None:
        _, client = setup
        resp = client.get("/admin/sessions", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200


class TestAdminEndpoints:
    def _auth(self) -> dict:
        return {"Authorization": "Bearer test-token"}

    def test_sessions_empty(self, setup) -> None:
        _, client = setup
        resp = client.get("/admin/sessions", headers=self._auth())
        data = resp.json()
        assert data["active_sessions"] == 0
        assert data["sessions"] == []

    def test_sessions_after_connect(self, setup) -> None:
        server, client = setup
        # Create a session via the game endpoint
        client.post("/api/command", json={"type": "command", "text": "hi"})

        resp = client.get("/admin/sessions", headers=self._auth())
        data = resp.json()
        assert data["active_sessions"] == 1

    def test_stats(self, setup) -> None:
        _, client = setup
        resp = client.get("/admin/stats", headers=self._auth())
        data = resp.json()
        assert "active_sessions" in data

    def test_kick_session(self, setup) -> None:
        server, client = setup
        # Create session
        resp = client.post("/api/command", json={"type": "command", "text": "hi"})
        session_id = resp.json()["session_id"]

        # Kick it
        resp = client.post("/admin/kick", json={"session_id": session_id}, headers=self._auth())
        assert resp.status_code == 200
        assert resp.json()["status"] == "kicked"

        # Verify gone
        resp = client.get("/admin/sessions", headers=self._auth())
        assert resp.json()["active_sessions"] == 0

    def test_kick_nonexistent(self, setup) -> None:
        _, client = setup
        resp = client.post("/admin/kick", json={"session_id": "fake"}, headers=self._auth())
        assert resp.status_code == 404
