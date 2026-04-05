"""Standalone textgame-io terminal client CLI.

Connects a terminal to any textgame-io-compatible server.
No game logic — purely the client adapter.

Usage:
    textgame connect <ws-url>          # connect with saved token
    textgame connect <ws-url> --lang it
    python -m textgame_io connect wss://example.com/ws
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

DEFAULT_TOKEN_PATH = Path(os.environ.get("TEXTWORLD_TOKEN_PATH", Path.home() / ".textworld" / "token"))


async def _connect(url: str, lang: str, art: bool, token_path: Path) -> None:
    from textgame_io.adapters.terminal import TerminalClient
    client = TerminalClient(server_url=url, lang=lang, art=art, token_path=token_path)
    await client.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="textgame-io terminal client — connect to any compatible server"
    )
    sub = parser.add_subparsers(dest="cmd")

    conn = sub.add_parser("connect", help="Connect to a server")
    conn.add_argument("url", help="WebSocket URL (e.g. wss://example.com/ws)")
    conn.add_argument("--lang", default="en", help="Language code (default: en)")
    conn.add_argument("--no-art", action="store_true", help="Disable ASCII art")
    conn.add_argument(
        "--token-path",
        type=Path,
        default=DEFAULT_TOKEN_PATH,
        help=f"Token file path (default: {DEFAULT_TOKEN_PATH})",
    )

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        return

    try:
        asyncio.run(_connect(args.url, args.lang, not args.no_art, args.token_path))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
