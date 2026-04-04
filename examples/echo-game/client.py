"""Terminal client for the echo game — demonstrates textgame-io client SDK."""

import asyncio

from textgame_io.adapters.terminal import run_terminal

if __name__ == "__main__":
    asyncio.run(run_terminal())
