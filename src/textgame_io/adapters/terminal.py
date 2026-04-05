"""Terminal client adapter — renders game messages with rich."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console

from textgame_io.client import GameClient
from textgame_io.messages import (
    ArtFormat,
    ArtMessage,
    AuthMessage,
    ClientType,
    NarrativeMessage,
    PromptMessage,
    PromptStyle,
    SessionConfig,
    StatusMessage,
    SystemLevel,
    SystemMessage,
)


class TerminalClient(GameClient):
    """Rich terminal client for any textgame-io server.

    token_path: if provided, the device token is read from this file on startup
    and written back whenever a new auth message is received. Allows the same
    character to reconnect across sessions without re-entering credentials.
    """

    def __init__(
        self,
        server_url: str = "ws://localhost:8000/ws",
        lang: str = "en",
        art: bool = True,
        token: str = "",
        token_path: Path | None = None,
    ) -> None:
        # Read saved token from file if none provided
        if not token and token_path and token_path.exists():
            token = token_path.read_text().strip()
        self._token_path = token_path
        super().__init__(server_url, token=token)
        self.console = Console()
        self.config = SessionConfig(
            lang=lang,
            art_enabled=art,
            art_format=ArtFormat.ASCII,
            prompt_style=PromptStyle.FREE_TEXT,
            client_type=ClientType.TERMINAL,
        )
        self._status: dict[str, str] = {}

    async def on_auth(self, msg: AuthMessage) -> None:
        """Persist the device token to disk so future sessions reconnect automatically."""
        if self._token_path:
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(msg.token)

    async def render_auth(self, msg: AuthMessage) -> None:
        await self.on_auth(msg)
        self.console.print("[bold yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]")
        if msg.recovery_phrase:
            self.console.print("[bold]  YOUR RECOVERY PHRASE — write this down![/bold]")
            self.console.print(f"  [bold cyan]{msg.recovery_phrase}[/bold cyan]")
            self.console.print("[dim]  You'll need this to link new devices.[/dim]")
        if self._token_path:
            self.console.print(f"[dim]  Token saved to {self._token_path}[/dim]")
        self.console.print("[bold yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]")

    async def render_narrative(self, msg: NarrativeMessage) -> None:
        if msg.title:
            self.console.print(f"[bold]{msg.title}[/bold]")
        if msg.text:
            self.console.print(msg.text)

    async def render_prompt(self, msg: PromptMessage) -> None:
        if msg.text:
            self.console.print(f"[dim]{msg.text}[/dim]")
        if msg.options and msg.style == PromptStyle.SELECT_ONE:
            for opt in msg.options:
                shortcut = f" ({opt.shortcut})" if opt.shortcut else ""
                self.console.print(f"  [cyan]{opt.label}[/cyan]{shortcut}")

    async def render_status(self, msg: StatusMessage) -> None:
        for field in msg.fields:
            self._status[field.key] = field.value
        # Don't print here — status bar renders once before the input prompt

    async def render_system(self, msg: SystemMessage) -> None:
        colors = {
            SystemLevel.INFO: "dim",
            SystemLevel.WARNING: "yellow",
            SystemLevel.ERROR: "red",
            SystemLevel.SUCCESS: "green",
        }
        color = colors.get(msg.level, "dim")
        self.console.print(f"[{color}]{msg.text}[/{color}]")

    async def render_art(self, msg: ArtMessage) -> None:
        if msg.format == ArtFormat.ASCII and msg.content:
            self.console.print(f"[dim]{msg.content}[/dim]")

    async def get_input(self) -> str:
        self._print_status_bar()
        return await asyncio.to_thread(self.console.input, "[bold cyan]> [/bold cyan]")

    def _print_status_bar(self) -> None:
        if not self._status:
            return
        parts = []
        for key in ["location", "zone", "hp", "version"]:
            val = self._status.get(key)
            if val:
                if key == "version":
                    parts.append(f"[dim cyan]{val}[/dim cyan]")
                elif key == "zone":
                    parts.append(f"[dim]{val}[/dim]")
                else:
                    parts.append(f"[bold white]{val}[/bold white]")
        bar = " [dim]|[/dim] ".join(parts)
        width = self.console.width
        self.console.print(f"[on grey11]{bar:^{width}}[/on grey11]", highlight=False)
