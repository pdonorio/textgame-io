"""Protocol message types — the contract between servers and clients.

Server → Client: NarrativeMessage, PromptMessage, StatusMessage, SystemMessage, ArtMessage
Client → Server: CommandMessage, ChoiceMessage, MetaMessage
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---


class MessageDirection(str, Enum):
    SERVER_TO_CLIENT = "s2c"
    CLIENT_TO_SERVER = "c2s"


class ServerMessageType(str, Enum):
    NARRATIVE = "narrative"
    PROMPT = "prompt"
    STATUS = "status"
    SYSTEM = "system"
    ART = "art"


class ClientMessageType(str, Enum):
    COMMAND = "command"
    CHOICE = "choice"
    META = "meta"


class SystemLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class ArtFormat(str, Enum):
    ASCII = "ascii"
    IMAGE_URL = "image_url"
    NONE = "none"


class MetaAction(str, Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RELOAD = "reload"
    PING = "ping"
    CONFIGURE = "configure"  # update session config mid-game


class PromptStyle(str, Enum):
    """How the client should present choices."""
    FREE_TEXT = "free_text"      # player types anything
    SELECT_ONE = "select_one"   # pick one from a list
    CONFIRM = "confirm"         # yes/no


# --- Session Config ---


class ClientType(str, Enum):
    """What kind of client is connecting."""
    TERMINAL = "terminal"
    TELEGRAM = "telegram"
    WEB = "web"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    GENERIC = "generic"


class SessionConfig(BaseModel):
    """Client preferences, sent on connect, stored per session by the server.

    The server uses these to tailor its responses:
    - lang: which locale to use for all text
    - art_format: what kind of art to send (ascii for terminal, image_url for chat, none to skip)
    - prompt_style: whether the client wants structured choices or free text
    - client_type: hint for server-side rendering decisions
    """
    lang: str = "en"
    art_enabled: bool = True
    art_format: ArtFormat = ArtFormat.ASCII
    prompt_style: PromptStyle = PromptStyle.FREE_TEXT
    client_type: ClientType = ClientType.GENERIC


# --- Server → Client ---


class NarrativeMessage(BaseModel):
    """Story text, room descriptions, NPC dialogue, combat narration."""
    type: ServerMessageType = ServerMessageType.NARRATIVE
    title: str = ""
    text: str
    style: str = ""  # optional hint: "room", "combat", "dialogue", "loot"


class PromptOption(BaseModel):
    """A single choice in a prompt."""
    key: str          # machine-readable ("north", "attack", "1")
    label: str        # human-readable ("Go North", "Attack the Ash Rat")
    shortcut: str = ""  # optional keyboard shortcut ("n", "a")


class PromptMessage(BaseModel):
    """Choices the player can make. Clients render as buttons, keyboard, or text."""
    type: ServerMessageType = ServerMessageType.PROMPT
    prompt_id: str                  # unique ID for this prompt (e.g., "exits", "combat_actions")
    text: str = ""                  # optional prompt text ("Where do you go?")
    style: PromptStyle = PromptStyle.FREE_TEXT
    options: list[PromptOption] = Field(default_factory=list)


class StatusField(BaseModel):
    """A single field in the status bar."""
    key: str      # "hp", "location", "zone", "version"
    label: str    # "HP", "Location"
    value: str    # "20/20", "Ruined Plaza"


class StatusMessage(BaseModel):
    """Status bar update. Clients decide how to render (bottom bar, header, pinned msg)."""
    type: ServerMessageType = ServerMessageType.STATUS
    fields: list[StatusField] = Field(default_factory=list)


class SystemMessage(BaseModel):
    """System messages: errors, confirmations, version info."""
    type: ServerMessageType = ServerMessageType.SYSTEM
    text: str
    level: SystemLevel = SystemLevel.INFO


class ArtMessage(BaseModel):
    """Visual content. Clients can render, convert, or skip."""
    type: ServerMessageType = ServerMessageType.ART
    format: ArtFormat = ArtFormat.ASCII
    content: str = ""   # ASCII art text or image URL
    alt: str = ""       # alt text description for accessibility


# Union of all server messages
ServerMessage = NarrativeMessage | PromptMessage | StatusMessage | SystemMessage | ArtMessage


# --- Client → Server ---


class CommandMessage(BaseModel):
    """Free text command from the player."""
    type: ClientMessageType = ClientMessageType.COMMAND
    text: str
    session_id: str = ""


class ChoiceMessage(BaseModel):
    """Structured choice in response to a PromptMessage."""
    type: ClientMessageType = ClientMessageType.CHOICE
    prompt_id: str       # matches the PromptMessage.prompt_id
    value: str           # the selected PromptOption.key
    session_id: str = ""


class MetaMessage(BaseModel):
    """Session control: connect, disconnect, reload."""
    type: ClientMessageType = ClientMessageType.META
    action: MetaAction
    session_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)  # e.g., {"lang": "it"}


# Union of all client messages
ClientMessage = CommandMessage | ChoiceMessage | MetaMessage


# --- Envelope ---


class Envelope(BaseModel):
    """Wire format wrapper. All messages are sent inside an envelope."""
    session_id: str = ""
    messages: list[ServerMessage | ClientMessage] = Field(default_factory=list)

    def add(self, msg: ServerMessage | ClientMessage) -> "Envelope":
        self.messages.append(msg)
        return self


# --- Message Parsing ---

# Type registries: map type string → model class. Add new message types here only.
_SERVER_MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    ServerMessageType.NARRATIVE: NarrativeMessage,
    ServerMessageType.PROMPT: PromptMessage,
    ServerMessageType.STATUS: StatusMessage,
    ServerMessageType.SYSTEM: SystemMessage,
    ServerMessageType.ART: ArtMessage,
}

_CLIENT_MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    ClientMessageType.COMMAND: CommandMessage,
    ClientMessageType.CHOICE: ChoiceMessage,
    ClientMessageType.META: MetaMessage,
}


def parse_server_message(data: dict) -> ServerMessage | None:
    """Parse a dict into a typed server message. Returns None if type is unknown."""
    model = _SERVER_MESSAGE_TYPES.get(data.get("type", ""))
    if model is None:
        return None
    try:
        return model(**data)
    except Exception:
        return None


def parse_client_message(data: dict) -> ClientMessage | None:
    """Parse a dict into a typed client message. Returns None if type is unknown."""
    model = _CLIENT_MESSAGE_TYPES.get(data.get("type", ""))
    if model is None:
        return None
    try:
        return model(**data)
    except Exception:
        return None
