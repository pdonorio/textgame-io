"""Tests for the base game server."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from textgame_io.messages import (
    NarrativeMessage,
    ServerMessage,
    SessionConfig,
    SystemMessage,
)
from textgame_io.server import GameServer, GameSession


class EchoServer(GameServer):
    """Minimal server for testing."""

    async def handle_connect(self, session: GameSession) -> list[ServerMessage]:
        return [NarrativeMessage(text="Welcome!")]

    async def handle_command(self, session: GameSession, text: str) -> list[ServerMessage]:
        return [NarrativeMessage(text=f"Echo: {text}")]


@pytest.fixture
def server() -> EchoServer:
    return EchoServer()


@pytest.fixture
def client(server: EchoServer) -> TestClient:
    return TestClient(server.as_asgi())


class TestSessionManagement:
    def test_create_session(self, server: EchoServer) -> None:
        session = server.create_session()
        assert session.session_id
        assert session.session_id in server.sessions

    def test_create_session_with_config(self, server: EchoServer) -> None:
        config = SessionConfig(lang="it")
        session = server.create_session(config)
        assert session.config.lang == "it"

    def test_get_session(self, server: EchoServer) -> None:
        session = server.create_session()
        found = server.get_session(session.session_id)
        assert found is session

    def test_get_missing_session(self, server: EchoServer) -> None:
        assert server.get_session("nonexistent") is None

    def test_remove_session(self, server: EchoServer) -> None:
        session = server.create_session()
        server.remove_session(session.session_id)
        assert session.session_id not in server.sessions


class TestHTTPEndpoint:
    def test_first_request_creates_session(self, client: TestClient) -> None:
        resp = client.post("/api/command", json={"type": "command", "text": "hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"]
        assert len(data["messages"]) > 0
        # First request returns welcome
        assert data["messages"][0]["text"] == "Welcome!"

    def test_subsequent_request_uses_session(self, client: TestClient) -> None:
        # Create session
        resp = client.post("/api/command", json={"type": "command", "text": "hello"})
        session_id = resp.json()["session_id"]

        # Send command with session
        resp = client.post("/api/command", json={
            "type": "command",
            "text": "test message",
            "session_id": session_id,
        })
        data = resp.json()
        assert data["session_id"] == session_id
        assert data["messages"][0]["text"] == "Echo: test message"

    def test_invalid_message(self, client: TestClient) -> None:
        # Create session first
        resp = client.post("/api/command", json={"type": "command", "text": "hi"})
        session_id = resp.json()["session_id"]

        # Send garbage
        resp = client.post("/api/command", json={
            "type": "bogus",
            "session_id": session_id,
        })
        data = resp.json()
        assert data["messages"][0]["level"] == "error"
