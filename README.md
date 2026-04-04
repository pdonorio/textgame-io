# textgame-io

Protocol and SDKs for connecting text game servers to any chat client.

Build a text game once, play it everywhere — terminal, Telegram, web, Discord, WhatsApp.

## Quick Start

```python
# Server
from textgame_io.server import GameServer, GameSession
from textgame_io.messages import NarrativeMessage

class MyGame(GameServer):
    async def handle_connect(self, session):
        return [NarrativeMessage(text="Welcome!")]

    async def handle_command(self, session, text):
        return [NarrativeMessage(text=f"You said: {text}")]

app = MyGame().as_asgi()
# Run with: uvicorn myserver:app
```

```python
# Client (terminal)
import asyncio
from textgame_io.adapters.terminal import run_terminal

asyncio.run(run_terminal("ws://localhost:8000/ws"))
```

## Protocol

See [protocol/spec.md](protocol/spec.md) for the full specification.

## License

MIT
