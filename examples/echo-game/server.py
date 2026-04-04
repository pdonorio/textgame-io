"""Simplest possible textgame-io server — echoes input back."""

import uvicorn

from textgame_io.admin import add_admin_routes
from textgame_io.messages import NarrativeMessage, ServerMessage, SystemMessage
from textgame_io.server import GameServer, GameSession


class EchoGame(GameServer):
    async def handle_connect(self, session: GameSession) -> list[ServerMessage]:
        return [
            NarrativeMessage(title="Echo Chamber", text="Everything you say echoes back. Type 'quit' to leave."),
        ]

    async def handle_command(self, session: GameSession, text: str) -> list[ServerMessage]:
        if text.lower() == "quit":
            return [SystemMessage(text="Goodbye!")]
        return [NarrativeMessage(text=f"Echo: {text}")]


if __name__ == "__main__":
    game = EchoGame()
    app = game.as_asgi()
    add_admin_routes(app, game, admin_token="secret")
    uvicorn.run(app, host="0.0.0.0", port=8000)
