# textgame-io Protocol Specification v0.1

## Overview

textgame-io is a protocol for connecting text game servers to any chat client (terminal, Telegram, web, Discord, etc.). The server sends structured data; clients render it however they want.

## Transport

- **WebSocket** `ws://host/ws` — real-time, bidirectional. For terminal and web clients.
- **HTTP** `POST /api/command` — request/response. For webhook-based clients (Telegram, WhatsApp).

Both transports use the same message format (JSON).

## Session Lifecycle

```
Client                          Server
  |                               |
  |--- connect (WebSocket) ------>|
  |                               |--- create session
  |<-- Envelope (welcome) --------|
  |                               |
  |--- CommandMessage ----------->|
  |<-- Envelope (response) -------|
  |                               |
  |--- ChoiceMessage ------------>|  (structured input, e.g., button tap)
  |<-- Envelope (response) -------|
  |                               |
  |--- MetaMessage(configure) --->|  (change lang, art, etc.)
  |<-- Envelope (confirmation) ---|
  |                               |
  |--- MetaMessage(disconnect) -->|
  |                               |--- persist state
  |<-- Envelope (goodbye) --------|
```

For HTTP: include `session_id` in each request. First request without session_id creates a new session.

## Message Types

### Envelope (wire format)

All messages are wrapped in an envelope:

```json
{
  "session_id": "abc123def456",
  "messages": [...]
}
```

### Server → Client

| Type | Fields | Purpose |
|------|--------|---------|
| `narrative` | title, text, style | Room descriptions, story, dialogue, combat |
| `prompt` | prompt_id, text, style, options[] | Choices: exits, combat actions, dialogue |
| `status` | fields[] | Status bar: HP, location, zone, version |
| `system` | text, level | Errors, confirmations, info |
| `art` | format, content, alt | ASCII art, image URL, or none |

### Client → Server

| Type | Fields | Purpose |
|------|--------|---------|
| `command` | text | Free text input ("go north") |
| `choice` | prompt_id, value | Structured pick ("exits", "north") |
| `meta` | action, payload | Session control (connect, configure, disconnect) |

### Session Config

Sent by client on connect or via `meta.configure`. Stored per session on server.

```json
{
  "lang": "en",
  "art_enabled": true,
  "art_format": "ascii",
  "prompt_style": "free_text",
  "client_type": "terminal"
}
```

| Field | Values | Default | Effect |
|-------|--------|---------|--------|
| lang | any locale code | "en" | Server translates all text |
| art_enabled | true/false | true | Whether to send art messages |
| art_format | ascii, image_url, none | ascii | What format art is sent in |
| prompt_style | free_text, select_one, confirm | free_text | How prompts are structured |
| client_type | terminal, telegram, web, whatsapp, discord, generic | generic | Server rendering hints |

### Prompt Options

When `prompt.style` is `select_one`, options are provided:

```json
{
  "type": "prompt",
  "prompt_id": "exits",
  "text": "Where do you go?",
  "style": "select_one",
  "options": [
    {"key": "north", "label": "Go North", "shortcut": "n"},
    {"key": "south", "label": "Go South", "shortcut": "s"}
  ]
}
```

Terminal: shows shortcuts. Telegram: inline keyboard buttons. Web: clickable buttons.

### Art Formats

| Format | Content | Use Case |
|--------|---------|----------|
| `ascii` | Raw ASCII art text | Terminal clients |
| `image_url` | URL to an image | Chat/web clients |
| `none` | Empty | Client doesn't want art |

## Admin API

Optional routes for server administration:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/sessions` | GET | List active sessions |
| `/admin/stats` | GET | Server stats |
| `/admin/kick` | POST | Disconnect a session |

Protected by `Authorization: Bearer <token>` header.

## Implementing a Server

```python
from textgame_io.server import GameServer, GameSession
from textgame_io.messages import NarrativeMessage, ServerMessage

class MyGame(GameServer):
    async def handle_connect(self, session):
        return [NarrativeMessage(text="Welcome to my game!")]

    async def handle_command(self, session, text):
        return [NarrativeMessage(text=f"You said: {text}")]
```

## Implementing a Client

```python
from textgame_io.client import GameClient
from textgame_io.messages import NarrativeMessage

class MyClient(GameClient):
    async def render_narrative(self, msg):
        print(msg.text)

    async def get_input(self):
        return input("> ")

    # ... implement other render methods
```
