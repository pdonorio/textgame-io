"""Base game server — any text game inherits this to get protocol support.

Subclass GameServer, implement handle_command/handle_choice/handle_connect,
and you get WebSocket + HTTP endpoints for free.
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Any

from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

_STATIC_DIR = Path(__file__).parent / "static"

from textgame_io.messages import (
    ChoiceMessage,
    ClientMessage,
    CommandMessage,
    Envelope,
    MetaAction,
    MetaMessage,
    ServerMessage,
    SessionConfig,
    SystemLevel,
    SystemMessage,
    parse_client_message,
)


class GameSession:
    """Server-side session for one connected player."""

    def __init__(self, session_id: str, config: SessionConfig | None = None, metadata: dict[str, Any] | None = None) -> None:
        self.session_id = session_id
        self.config = config or SessionConfig()
        self.state: dict[str, Any] = {}  # game-specific state, set by subclass
        self.metadata: dict[str, Any] = metadata or {}  # transport-level info (token, client hints)
        self._outbox: asyncio.Queue[list[ServerMessage]] = asyncio.Queue()  # server-push messages


class GameServer(ABC):
    """Base class for text game servers.

    Subclass and implement:
      - handle_connect(session) -> list[ServerMessage]
      - handle_command(session, text) -> list[ServerMessage]
      - handle_choice(session, prompt_id, value) -> list[ServerMessage]
      - handle_disconnect(session) -> None
      - handle_configure(session, config) -> list[ServerMessage]  (optional)
    """

    def __init__(self) -> None:
        self.sessions: dict[str, GameSession] = {}

    # --- Abstract methods for game logic ---

    @abstractmethod
    async def handle_connect(self, session: GameSession) -> list[ServerMessage]:
        """Called when a new client connects. Return welcome messages."""

    @abstractmethod
    async def handle_command(self, session: GameSession, text: str) -> list[ServerMessage]:
        """Called when a client sends free text. Return response messages."""

    async def handle_choice(self, session: GameSession, prompt_id: str, value: str) -> list[ServerMessage]:
        """Called when a client picks a structured choice. Default: treat as command."""
        return await self.handle_command(session, value)

    async def handle_disconnect(self, session: GameSession) -> None:
        """Called when a client disconnects. Override to persist state."""

    async def handle_configure(self, session: GameSession, config: SessionConfig) -> list[ServerMessage]:
        """Called when a client updates its config. Override for custom behavior."""
        session.config = config
        return [SystemMessage(text="Configuration updated.", level=SystemLevel.SUCCESS)]

    # --- Session management ---

    def create_session(self, config: SessionConfig | None = None, metadata: dict[str, Any] | None = None) -> GameSession:
        session_id = uuid.uuid4().hex[:12]
        session = GameSession(session_id, config, metadata)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> GameSession | None:
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    # --- Message routing ---

    async def _enqueue(self, session: GameSession, messages: list[ServerMessage]) -> None:
        """Push server-initiated messages to the session's outbox."""
        await session._outbox.put(messages)

    async def route_message(self, session: GameSession, msg: ClientMessage) -> list[ServerMessage]:
        """Route an incoming client message to the appropriate handler."""
        if isinstance(msg, CommandMessage):
            return await self.handle_command(session, msg.text)
        elif isinstance(msg, ChoiceMessage):
            return await self.handle_choice(session, msg.prompt_id, msg.value)
        elif isinstance(msg, MetaMessage):
            if msg.action == MetaAction.CONFIGURE:
                config = SessionConfig(**msg.payload)
                return await self.handle_configure(session, config)
            elif msg.action == MetaAction.DISCONNECT:
                await self.handle_disconnect(session)
                return [SystemMessage(text="Disconnected.", level=SystemLevel.INFO)]
            elif msg.action == MetaAction.PING:
                return [SystemMessage(text="pong", level=SystemLevel.INFO)]
        return [SystemMessage(text="Unknown message type.", level=SystemLevel.ERROR)]

    # --- Starlette app ---

    def as_asgi(self) -> Starlette:
        """Return a Starlette ASGI app with WebSocket and HTTP endpoints."""

        async def websocket_endpoint(ws: WebSocket) -> None:
            await ws.accept()
            # Extract query params as session metadata
            params = dict(ws.query_params)
            metadata: dict[str, Any] = {}
            if "token" in params:
                metadata["token"] = params["token"]
            # art=false disables art for this session (e.g. mobile clients)
            config = SessionConfig()
            if params.get("art") == "false":
                config.art_enabled = False
            session = self.create_session(config=config, metadata=metadata)
            try:
                # Send welcome
                try:
                    welcome = await self.handle_connect(session)
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).exception("handle_connect failed")
                    welcome = [SystemMessage(text=f"Connection error: {exc}", level=SystemLevel.ERROR)]
                envelope = Envelope(session_id=session.session_id, messages=welcome)
                await ws.send_json(envelope.model_dump())

                # Main loop — wait for client input OR server-push messages
                while True:
                    receive_task = asyncio.create_task(ws.receive_json())
                    push_task = asyncio.create_task(session._outbox.get())
                    done, pending = await asyncio.wait(
                        [receive_task, push_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                        try:
                            await t
                        except (asyncio.CancelledError, Exception):
                            pass

                    if push_task in done:
                        push_msgs = push_task.result()
                        push_env = Envelope(session_id=session.session_id, messages=push_msgs)
                        await ws.send_json(push_env.model_dump())

                    if receive_task in done:
                        data = receive_task.result()
                        client_msg = parse_client_message(data)
                        if client_msg is None:
                            err = Envelope(
                                session_id=session.session_id,
                                messages=[SystemMessage(text="Invalid message.", level=SystemLevel.ERROR)],
                            )
                            await ws.send_json(err.model_dump())
                            continue

                        try:
                            responses = await self.route_message(session, client_msg)
                        except Exception as exc:
                            responses = [SystemMessage(
                                text=f"Internal error: {exc}",
                                level=SystemLevel.ERROR,
                            )]
                        envelope = Envelope(session_id=session.session_id, messages=responses)
                        await ws.send_json(envelope.model_dump())
            except WebSocketDisconnect:
                await self.handle_disconnect(session)
                self.remove_session(session.session_id)

        async def http_command(request: Request) -> JSONResponse:
            data = await request.json()
            session_id = data.get("session_id", "")

            # Connect flow
            if not session_id or session_id not in self.sessions:
                config = SessionConfig(**data.get("config", {}))
                metadata: dict[str, Any] = {}
                if "token" in data:
                    metadata["token"] = data["token"]
                session = self.create_session(config, metadata=metadata)
                welcome = await self.handle_connect(session)
                envelope = Envelope(session_id=session.session_id, messages=welcome)
                return JSONResponse(envelope.model_dump())

            session = self.sessions[session_id]
            client_msg = parse_client_message(data)
            if client_msg is None:
                envelope = Envelope(
                    session_id=session_id,
                    messages=[SystemMessage(text="Invalid message.", level=SystemLevel.ERROR)],
                )
                return JSONResponse(envelope.model_dump())

            responses = await self.route_message(session, client_msg)
            envelope = Envelope(session_id=session.session_id, messages=responses)
            return JSONResponse(envelope.model_dump())

        async def serve_index(request: Request) -> FileResponse:
            return FileResponse(_STATIC_DIR / "index.html")

        routes = [
            Route("/", serve_index, methods=["GET"]),
            Route("/api/command", http_command, methods=["POST"]),
            WebSocketRoute("/ws", websocket_endpoint),
            Mount("/static", StaticFiles(directory=_STATIC_DIR)),
        ]

        app = Starlette(routes=routes)
        return app
