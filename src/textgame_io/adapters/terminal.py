"""Terminal client adapter — renders game messages with rich."""

from __future__ import annotations

import asyncio

from rich.console import Console

from textgame_io.client import GameClient
from textgame_io.messages import (
    ArtFormat,
    ArtMessage,
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
    """Rich terminal client for any textgame-io server."""

    def __init__(self, server_url: str = "ws://localhost:8000/ws", lang: str = "en", art: bool = True) -> None:
        super().__init__(server_url)
        self.console = Console()
        self.config = SessionConfig(
            lang=lang,
            art_enabled=art,
            art_format=ArtFormat.ASCII,
            prompt_style=PromptStyle.FREE_TEXT,
            client_type=ClientType.TERMINAL,
        )
        self._status: dict[str, str] = {}

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


async def run_terminal(server_url: str = "ws://localhost:8000/ws", lang: str = "en", art: bool = True) -> None:
    """Convenience function to run the terminal client."""
    client = TerminalClient(server_url=server_url, lang=lang, art=art)
    await client.run()
