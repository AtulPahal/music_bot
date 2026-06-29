#!/usr/bin/env python3
"""Entry point — python -m bot"""

import asyncio
import ctypes.util
import logging
import os
import sys

import discord

from bot.config import Config, ConfigError
from bot.services.ytmusic import YTMusicService


def _load_opus() -> None:
    """Locate and load libopus, required by discord.py for audio encoding."""
    if discord.opus.is_loaded():
        return

    # Common locations on macOS (Homebrew) and Linux
    candidates = [
        ctypes.util.find_library("opus"),
        os.environ.get("DISCORD_OPUS_LIB"),
        "/opt/homebrew/lib/libopus.0.dylib",
        "/usr/local/lib/libopus.0.dylib",
        "/opt/homebrew/lib/libopus.dylib",
        "/usr/local/lib/libopus.dylib",
        "/usr/lib/x86_64-linux-gnu/libopus.so.0",
        "/usr/lib/aarch64-linux-gnu/libopus.so.0",
        "/usr/lib/libopus.so.0",
    ]

    for path in candidates:
        if path and os.path.exists(path):
            try:
                discord.opus.load_opus(path)
                logging.getLogger("bot").info("Loaded libopus from %s", path)
                return
            except Exception as e:
                logging.getLogger("bot").debug("Failed to load opus from %s: %s", path, e)

    logging.getLogger("bot").warning(
        "libopus not found. Audio playback requires libopus. "
        "Install it: brew install opus (macOS) or apt install libopus0 (Linux)."
    )


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main() -> None:
    # Load libopus before anything else (discord.py needs it for voice)
    _load_opus()

    # Load config (validates required env vars)
    try:
        config = Config()
    except ConfigError as e:
        print(f"Configuration error:\n{e}")
        print("Copy .env.example to .env and fill in the required values.")
        sys.exit(1)

    setup_logging(config.LOG_LEVEL)
    log = logging.getLogger("bot")

    # Initialize bot
    from bot.bot import MusicBot

    bot = MusicBot(config)

    # Initialize YTMusic service (graceful fallback if no credentials)
    ytmusic = YTMusicService()
    ytmusic.initialize(
        auth_file=config.YTM_AUTH_FILE,
        auth_mode=config.YTM_AUTH_MODE,
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
    )
    bot.ytmusic = ytmusic
    if ytmusic.available:
        log.info("YTMusic service ready")
    else:
        log.warning("YTMusic service unavailable — search/playlist features disabled.")
        bot.ytmusic = None

    # Start bot
    try:
        await bot.start(config.DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        await bot.close()
    except discord.PrivilegedIntentsRequired:
        log.critical(
            "The bot needs privileged intents enabled in the Discord Developer Portal.\n"
            "Go to https://discord.com/developers/applications → your app → Bot →\n"
            "enable **Message Content Intent** and **Voice States Intent**."
        )
        await bot.close()
        sys.exit(1)
    except Exception as e:
        log.critical("Fatal error: %s", e)
        await bot.close()
        sys.exit(1)


def entry_point() -> None:
    """Synchronous entry point for `uv run music-bot` / `music-bot` CLI."""
    asyncio.run(main())


if __name__ == "__main__":
    entry_point()
