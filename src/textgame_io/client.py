"""Base game client — subclass to build terminal, Telegram, web, etc. adapters.

A client connects to a game server, sends commands/choices, and renders responses.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

import websockets
from websockets.asyncio.client import ClientConnection

from textgame_io.messages import (
    ArtMessage,
    AuthMessage,
    ClientMessage,
    CommandMessage,
    Envelope,
    MetaAction,
    MetaMessage,
    NarrativeMessage,
    PromptMessage,
    ServerMessage,
    SessionConfig,
    StatusMessage,
    SystemMessage,
    parse_server_message,
)


class GameClient(ABC):
    """Base class for text game clients.

    Subclass and implement the render_* methods for your platform.
    Then call run() to connect and start the game loop.

    Pass token to authenticate as an existing character. The token is
    appended to the WebSocket URL as ?token=<hex>. Override on_auth()
    to persist a newly issued token for future sessions.
    """

    def __init__(self, server_url: str = "ws://localhost:8000/ws", token: str = "") -> None:
        # Append auth token to URL if provided
        if token:
            sep = "&" if "?" in server_url else "?"
            server_url = f"{server_url}{sep}token={token}"
        self.server_url = server_url
        self.session_id: str = ""
        self.config = SessionConfig()
        self._ws: ClientConnection | None = None

    # --- Abstract: platform-specific rendering ---

    @abstractmethod
    async def render_narrative(self, msg: NarrativeMessage) -> None:
        """Render story text, room descriptions, combat narration."""

    @abstractmethod
    async def render_prompt(self, msg: PromptMessage) -> None:
        """Render choices (buttons, text, etc.)."""

    @abstractmethod
    async def render_status(self, msg: StatusMessage) -> None:
        """Render status bar / header."""

    @abstractmethod
    async def render_system(self, msg: SystemMessage) -> None:
        """Render system messages (errors, confirmations)."""

    @abstractmethod
    async def render_art(self, msg: ArtMessage) -> None:
        """Render visual content (ASCII art, image, or skip)."""

    async def on_auth(self, msg: AuthMessage) -> None:
        """Called when an auth message is received. Override to persist the token."""

    async def render_auth(self, msg: AuthMessage) -> None:
        """Handle auth message. Calls on_auth() then displays recovery phrase if present."""
        await self.on_auth(msg)

    @abstractmethod
    async def get_input(self) -> str:
        """Wait for player input. Returns raw text."""

    async def on_connect(self) -> None:
        """Called after connection is established. Override for setup."""

    async def on_disconnect(self) -> None:
        """Called after disconnection. Override for cleanup."""

    # --- Message rendering dispatch ---

    async def render_message(self, msg: ServerMessage) -> None:
        """Route a server message to the appropriate render method."""
        if isinstance(msg, NarrativeMessage):
            await self.render_narrative(msg)
        elif isinstance(msg, PromptMessage):
            await self.render_prompt(msg)
        elif isinstance(msg, StatusMessage):
            await self.render_status(msg)
        elif isinstance(msg, SystemMessage):
            await self.render_system(msg)
        elif isinstance(msg, ArtMessage):
            await self.render_art(msg)
        elif isinstance(msg, AuthMessage):
            await self.render_auth(msg)

    async def render_envelope(self, envelope: Envelope) -> None:
        """Render all messages in an envelope."""
        for msg_data in envelope.messages:
            # Re-parse from dict since union deserialization needs type dispatch
            msg = parse_server_message(msg_data) if isinstance(msg_data, dict) else msg_data
            if msg:
                await self.render_message(msg)

    # --- Network ---

    async def send(self, msg: ClientMessage) -> Envelope:
        """Send a message and receive the response envelope."""
        if not self._ws:
            raise RuntimeError("Not connected")
        msg.session_id = self.session_id
        await self._ws.send(json.dumps(msg.model_dump()))
        raw = await self._ws.recv()
        data = json.loads(raw)
        return Envelope(**data)

    async def connect(self) -> Envelope:
        """Connect to the server via WebSocket."""
        self._ws = await websockets.connect(self.server_url)
        # Server sends welcome envelope immediately after connect
        raw = await self._ws.recv()
        data = json.loads(raw)
        envelope = Envelope(**data)
        self.session_id = envelope.session_id
        await self.on_connect()
        return envelope

    async def disconnect(self) -> None:
        """Cleanly disconnect from the server."""
        if self._ws:
            try:
                await self.send(MetaMessage(action=MetaAction.DISCONNECT))
            except Exception:
                pass
            await self._ws.close()
            self._ws = None
        await self.on_disconnect()

    # --- Main loop ---

    async def run(self) -> None:
        """Connect, render welcome, then loop: get input → send → render."""
        envelope = await self.connect()
        await self.render_envelope(envelope)

        try:
            while True:
                text = await self.get_input()
                if not text:
                    continue
                msg = CommandMessage(text=text)
                envelope = await self.send(msg)
                await self.render_envelope(envelope)
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            await self.disconnect()


