#!/usr/bin/env python3
"""Main executable entry point for MusicBot with dynamic libopus loading and lifecycle orchestration."""

from __future__ import annotations

import asyncio
import ctypes.util
import logging
import os
import signal
import sys
from typing import Optional

import discord

from bot.config import Config, ConfigError
from bot.services.ytmusic import YTMusicService


def _load_opus(custom_path: str = "") -> None:
    """Locate and load libopus required by discord.py for voice encoding."""
    if discord.opus.is_loaded():
        return

    candidates: list[Optional[str]] = [
        custom_path,
        os.environ.get("DISCORD_OPUS_LIB"),
        ctypes.util.find_library("opus"),
        ctypes.util.find_library("libopus"),
        "/opt/homebrew/lib/libopus.0.dylib",
        "/usr/local/lib/libopus.0.dylib",
        "/opt/homebrew/lib/libopus.dylib",
        "/usr/local/lib/libopus.dylib",
        "/usr/lib/x86_64-linux-gnu/libopus.so.0",
        "/usr/lib/aarch64-linux-gnu/libopus.so.0",
        "/usr/lib/libopus.so.0",
        "libopus.so.0",
        "libopus-0.dll",
    ]

    for path in candidates:
        if not path:
            continue
        try:
            if "/" not in path and "\\" not in path:
                discord.opus.load_opus(path)
                logging.getLogger("bot").info("Loaded libopus library: %s", path)
                return
            elif os.path.exists(path):
                discord.opus.load_opus(path)
                logging.getLogger("bot").info("Loaded libopus from path: %s", path)
                return
        except Exception as e:
            logging.getLogger("bot").debug("Could not load opus candidate %s: %s", path, e)

    logging.getLogger("bot").warning(
        "libopus was not found. Voice playback will require libopus. "
        "Install via `brew install opus` (macOS) or `apt install libopus0` (Linux)."
    )


def setup_logging(level: str) -> None:
    """Configure root and bot logger formatting."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main() -> None:
    """Asynchronous entry point for application initialization."""
    # 1. Load Configuration
    try:
        config = Config()
    except ConfigError as err:
        print(f"Configuration Error:\n{err}\nPlease verify your .env configuration.", file=sys.stderr)
        sys.exit(1)

    setup_logging(config.discord.log_level)
    log = logging.getLogger("bot")

    # 2. Load Opus Audio Library
    _load_opus(config.voice.libopus_path)

    # 3. Initialize Bot Instance
    from bot.bot import MusicBot

    bot = MusicBot(config)

    # 4. Initialize YTMusic Service
    ytmusic = YTMusicService(max_workers=config.ytmusic.max_workers)
    ytmusic.initialize(
        auth_file=config.ytmusic.auth_file,
        auth_mode=config.ytmusic.auth_mode,
        client_id=config.ytmusic.google_client_id,
        client_secret=config.ytmusic.google_client_secret,
    )
    bot.ytmusic = ytmusic

    # 5. Start Bot with Exception Handling
    try:
        await bot.start(config.discord.bot_token)
    except KeyboardInterrupt:
        log.info("Shutdown requested via KeyboardInterrupt.")
    except discord.PrivilegedIntentsRequired:
        log.critical(
            "Privileged intents are required in the Discord Developer Portal.\n"
            "Enable 'Message Content Intent' and 'Voice States Intent' at https://discord.com/developers/applications."
        )
    except Exception as exc:
        log.critical("Fatal error encountered: %s", exc)
    finally:
        if not bot.is_closed():
            await bot.close()


def entry_point() -> None:
    """CLI synchronous entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    entry_point()
