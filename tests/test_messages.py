"""Tests for protocol message types."""

from __future__ import annotations

from textgame_io.messages import (
    ArtFormat,
    ArtMessage,
    ChoiceMessage,
    ClientType,
    CommandMessage,
    Envelope,
    MetaAction,
    MetaMessage,
    NarrativeMessage,
    PromptMessage,
    PromptOption,
    PromptStyle,
    SessionConfig,
    StatusField,
    StatusMessage,
    SystemLevel,
    SystemMessage,
)


class TestNarrativeMessage:
    def test_basic(self) -> None:
        msg = NarrativeMessage(text="Hello world")
        assert msg.type == "narrative"
        assert msg.text == "Hello world"
        assert msg.title == ""

    def test_with_title_and_style(self) -> None:
        msg = NarrativeMessage(title="Room", text="A dark room.", style="room")
        assert msg.title == "Room"
        assert msg.style == "room"

    def test_serialization_roundtrip(self) -> None:
        msg = NarrativeMessage(title="Test", text="Content")
        data = msg.model_dump()
        restored = NarrativeMessage(**data)
        assert restored.title == "Test"
        assert restored.text == "Content"


class TestPromptMessage:
    def test_free_text(self) -> None:
        msg = PromptMessage(prompt_id="exits", text="Where?")
        assert msg.style == PromptStyle.FREE_TEXT
        assert msg.options == []

    def test_select_one(self) -> None:
        msg = PromptMessage(
            prompt_id="exits",
            style=PromptStyle.SELECT_ONE,
            options=[
                PromptOption(key="north", label="Go North", shortcut="n"),
                PromptOption(key="south", label="Go South", shortcut="s"),
            ],
        )
        assert len(msg.options) == 2
        assert msg.options[0].key == "north"


class TestStatusMessage:
    def test_fields(self) -> None:
        msg = StatusMessage(fields=[
            StatusField(key="location", label="Location", value="Plaza"),
            StatusField(key="hp", label="HP", value="20/20"),
        ])
        assert len(msg.fields) == 2
        assert msg.fields[0].value == "Plaza"


class TestSystemMessage:
    def test_error(self) -> None:
        msg = SystemMessage(text="Something broke", level=SystemLevel.ERROR)
        assert msg.level == SystemLevel.ERROR

    def test_defaults_to_info(self) -> None:
        msg = SystemMessage(text="OK")
        assert msg.level == SystemLevel.INFO


class TestArtMessage:
    def test_ascii(self) -> None:
        msg = ArtMessage(format=ArtFormat.ASCII, content="  /\\\n /  \\", alt="A house")
        assert msg.format == ArtFormat.ASCII
        assert msg.alt == "A house"

    def test_image_url(self) -> None:
        msg = ArtMessage(format=ArtFormat.IMAGE_URL, content="https://example.com/art.png")
        assert msg.format == ArtFormat.IMAGE_URL


class TestClientMessages:
    def test_command(self) -> None:
        msg = CommandMessage(text="go north", session_id="abc")
        assert msg.type == "command"
        assert msg.text == "go north"

    def test_choice(self) -> None:
        msg = ChoiceMessage(prompt_id="exits", value="north")
        assert msg.type == "choice"

    def test_meta_connect(self) -> None:
        msg = MetaMessage(action=MetaAction.CONNECT, payload={"lang": "it"})
        assert msg.action == MetaAction.CONNECT
        assert msg.payload["lang"] == "it"

    def test_meta_configure(self) -> None:
        msg = MetaMessage(action=MetaAction.CONFIGURE, payload={"lang": "it", "art_enabled": False})
        assert msg.action == MetaAction.CONFIGURE


class TestSessionConfig:
    def test_defaults(self) -> None:
        cfg = SessionConfig()
        assert cfg.lang == "en"
        assert cfg.art_enabled is True
        assert cfg.art_format == ArtFormat.ASCII
        assert cfg.client_type == ClientType.GENERIC

    def test_telegram_config(self) -> None:
        cfg = SessionConfig(
            lang="it",
            art_format=ArtFormat.IMAGE_URL,
            prompt_style=PromptStyle.SELECT_ONE,
            client_type=ClientType.TELEGRAM,
        )
        assert cfg.client_type == ClientType.TELEGRAM
        assert cfg.prompt_style == PromptStyle.SELECT_ONE


class TestEnvelope:
    def test_empty(self) -> None:
        env = Envelope(session_id="abc")
        assert env.messages == []

    def test_add(self) -> None:
        env = Envelope(session_id="abc")
        env.add(NarrativeMessage(text="Hello"))
        env.add(StatusMessage(fields=[]))
        assert len(env.messages) == 2

    def test_serialization(self) -> None:
        env = Envelope(session_id="abc")
        env.add(NarrativeMessage(text="Hello"))
        data = env.model_dump()
        assert data["session_id"] == "abc"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["type"] == "narrative"
