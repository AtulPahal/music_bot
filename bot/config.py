"""Configuration management for MusicBot with modular typed settings and environment validation."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import discord
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


def _clean_env(key: str, default: str = "") -> str:
    """Read an environment variable, stripping inline comments and whitespace."""
    val = os.getenv(key, default)
    if not val:
        return default
    val = val.strip()
    if val.startswith("#"):
        return default
    if " #" in val:
        val = val.split(" #", 1)[0]
    return val.strip()


def _parse_bool(val: str, default: bool = False) -> bool:
    """Parse a boolean value from string."""
    if not val:
        return default
    return val.lower() in ("true", "1", "yes", "on", "t", "y")


def _parse_int(val: str, default: int = 0) -> int:
    """Parse an integer value with default fallback."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _parse_float(val: str, default: float = 0.0) -> float:
    """Parse a float value with default fallback."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_int_list(val: str) -> list[int]:
    """Parse a comma-separated list of integers."""
    if not val:
        return []
    res: list[int] = []
    for item in val.split(","):
        clean = item.strip()
        if clean.isdigit():
            res.append(int(clean))
    return res


def _parse_str_list(val: str, default: list[str]) -> list[str]:
    """Parse a comma-separated list of strings."""
    if not val:
        return default
    items = [item.strip() for item in val.split(",") if item.strip()]
    return items if items else default


def _parse_color(val: str, default: int) -> discord.Color:
    """Parse a hex color or integer into discord.Color."""
    if not val:
        return discord.Color(default)
    clean = val.strip().lstrip("#")
    try:
        if clean.startswith("0x") or clean.startswith("0X"):
            return discord.Color(int(clean, 16))
        return discord.Color(int(clean, 16))
    except (ValueError, TypeError):
        return discord.Color(default)


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass
class DiscordConfig:
    """Discord connection, bot identity, and optional web healthcheck port configuration."""

    bot_token: str = field(default_factory=lambda: _clean_env("DISCORD_BOT_TOKEN"))
    client_id: str = field(default_factory=lambda: _clean_env("DISCORD_CLIENT_ID"))
    guild_id: int = field(default_factory=lambda: _parse_int(_clean_env("DISCORD_GUILD_ID", "0")))
    app_name: str = field(default_factory=lambda: _clean_env("DISCORD_APP_NAME", "Music Bot"))
    command_prefix: str = field(default_factory=lambda: _clean_env("COMMAND_PREFIX", "!"))
    owner_ids: list[int] = field(default_factory=lambda: _parse_int_list(_clean_env("OWNER_IDS", "")))
    log_level: str = field(default_factory=lambda: _clean_env("LOG_LEVEL", "INFO").upper())
    activity_type: str = field(default_factory=lambda: _clean_env("ACTIVITY_TYPE", "listening").lower())
    activity_name: str = field(default_factory=lambda: _clean_env("ACTIVITY_NAME", "{prefix}play | {app_name}"))
    presence_status: str = field(default_factory=lambda: _clean_env("PRESENCE_STATUS", "online").lower())
    port: int = field(
        default_factory=lambda: _parse_int(
            _clean_env("PORT", _clean_env("HEALTH_PORT", "0")), 0
        )
    )


@dataclass
class VoiceConfig:
    """Voice channel, timeout, and volume limits configuration."""

    default_volume: float = field(default_factory=lambda: _parse_float(_clean_env("DEFAULT_VOLUME", "0.5"), 0.5))
    min_volume: float = field(default_factory=lambda: _parse_float(_clean_env("MIN_VOLUME", "0.0"), 0.0))
    max_volume: float = field(default_factory=lambda: _parse_float(_clean_env("MAX_VOLUME", "2.0"), 2.0))
    max_queue_length: int = field(default_factory=lambda: _parse_int(_clean_env("MAX_QUEUE_LENGTH", "500"), 500))
    auto_disconnect_timeout: int = field(
        default_factory=lambda: _parse_int(_clean_env("AUTO_DISCONNECT_TIMEOUT", "300"), 300)
    )
    connect_timeout: float = field(
        default_factory=lambda: _parse_float(_clean_env("CONNECT_TIMEOUT", "20.0"), 20.0)
    )
    libopus_path: str = field(default_factory=lambda: _clean_env("DISCORD_OPUS_LIB", ""))


@dataclass
class AudioConfig:
    """FFmpeg and yt-dlp audio stream extraction configuration."""

    ffmpeg_bin: str = field(default_factory=lambda: _clean_env("FFMPEG_BIN", "ffmpeg"))
    ffmpeg_before_options: str = field(
        default_factory=lambda: _clean_env(
            "FFMPEG_BEFORE_OPTIONS",
            "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        )
    )
    ffmpeg_options: str = field(
        default_factory=lambda: _clean_env("FFMPEG_OPTIONS", "-vn -bufsize 64k")
    )
    ytdl_format: str = field(default_factory=lambda: _clean_env("YTDL_FORMAT", "bestaudio/best"))
    ytdl_proxy: str = field(default_factory=lambda: _clean_env("YT_PROXY", ""))
    ytdl_cookies_file: str = field(default_factory=lambda: _clean_env("YTDL_COOKIES_FILE", ""))
    ytdl_cookies_text: str = field(
        default_factory=lambda: _clean_env("YTDL_COOKIES", _clean_env("YTDL_COOKIES_TEXT", ""))
    )
    ytdl_default_search: str = field(default_factory=lambda: _clean_env("YTDL_DEFAULT_SEARCH", "ytsearch"))
    ytdl_socket_timeout: int = field(
        default_factory=lambda: _parse_int(_clean_env("YTDL_SOCKET_TIMEOUT", "15"), 15)
    )
    ytdl_user_agent: str = field(default_factory=lambda: _clean_env("YTDL_USER_AGENT", ""))
    ytdl_player_clients: list[str] = field(
        default_factory=lambda: _parse_str_list(
            _clean_env("YTDL_PLAYER_CLIENTS", "android,ios,mweb,web"),
            ["android", "ios", "mweb", "web"],
        )
    )
    ytdl_po_token: str = field(default_factory=lambda: _clean_env("YTDL_PO_TOKEN", ""))


@dataclass
class YTMusicConfig:
    """YouTube Music API service configuration."""

    auth_file: str = field(default_factory=lambda: _clean_env("YTM_AUTH_FILE", "data/oauth.json"))
    auth_mode: str = field(default_factory=lambda: _clean_env("YTM_AUTH_MODE", "none").lower())
    google_client_id: str = field(default_factory=lambda: _clean_env("GOOGLE_CLIENT_ID", ""))
    google_client_secret: str = field(default_factory=lambda: _clean_env("GOOGLE_CLIENT_SECRET", ""))
    radio_enabled: bool = field(
        default_factory=lambda: _parse_bool(_clean_env("YT_RADIO_ENABLED", "true"), True)
    )
    suggestion_timeout: int = field(
        default_factory=lambda: _parse_int(_clean_env("SUGGESTION_TIMEOUT", "30"), 30)
    )
    search_limit: int = field(default_factory=lambda: _parse_int(_clean_env("SEARCH_LIMIT", "10"), 10))
    max_workers: int = field(default_factory=lambda: _parse_int(_clean_env("YTM_MAX_WORKERS", "4"), 4))


@dataclass
class UIThemeConfig:
    """UI theme colors and component timings."""

    color_primary: discord.Color = field(
        default_factory=lambda: _parse_color(_clean_env("COLOR_PRIMARY", "5865F2"), 0x5865F2)
    )
    color_success: discord.Color = field(
        default_factory=lambda: _parse_color(_clean_env("COLOR_SUCCESS", "57F287"), 0x57F287)
    )
    color_warning: discord.Color = field(
        default_factory=lambda: _parse_color(_clean_env("COLOR_WARNING", "FEE75C"), 0xFEE75C)
    )
    color_error: discord.Color = field(
        default_factory=lambda: _parse_color(_clean_env("COLOR_ERROR", "ED4245"), 0xED4245)
    )
    color_secondary: discord.Color = field(
        default_factory=lambda: _parse_color(_clean_env("COLOR_SECONDARY", "EB459E"), 0xEB459E)
    )
    color_queue: discord.Color = field(
        default_factory=lambda: _parse_color(_clean_env("COLOR_QUEUE", "5865F2"), 0x5865F2)
    )
    color_history: discord.Color = field(
        default_factory=lambda: _parse_color(_clean_env("COLOR_HISTORY", "9B59B6"), 0x9B59B6)
    )
    footer_text: str = field(default_factory=lambda: _clean_env("FOOTER_TEXT", ""))
    queue_page_size: int = field(default_factory=lambda: _parse_int(_clean_env("QUEUE_PAGE_SIZE", "10"), 10))
    button_timeout: Optional[float] = field(
        default_factory=lambda: (
            None
            if _clean_env("BUTTON_TIMEOUT", "").lower() in ("none", "0", "")
            else _parse_float(_clean_env("BUTTON_TIMEOUT", "180"), 180.0)
        )
    )


@dataclass
class Config:
    """Unified configuration container with typed modular sections."""

    discord: DiscordConfig = field(default_factory=DiscordConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    ytmusic: YTMusicConfig = field(default_factory=YTMusicConfig)
    ui: UIThemeConfig = field(default_factory=UIThemeConfig)

    # --- Backwards compatibility properties ---

    @property
    def DISCORD_BOT_TOKEN(self) -> str:
        return self.discord.bot_token

    @property
    def DISCORD_CLIENT_ID(self) -> str:
        return self.discord.client_id

    @property
    def DISCORD_GUILD_ID(self) -> int:
        return self.discord.guild_id

    @property
    def DISCORD_APP_NAME(self) -> str:
        return self.discord.app_name

    @property
    def COMMAND_PREFIX(self) -> str:
        return self.discord.command_prefix

    @property
    def OWNER_IDS(self) -> list[int]:
        return self.discord.owner_ids

    @property
    def LOG_LEVEL(self) -> str:
        return self.discord.log_level

    @property
    def YTM_AUTH_FILE(self) -> str:
        return self.ytmusic.auth_file

    @property
    def YTM_AUTH_MODE(self) -> str:
        return self.ytmusic.auth_mode

    @property
    def GOOGLE_CLIENT_ID(self) -> str:
        return self.ytmusic.google_client_id

    @property
    def GOOGLE_CLIENT_SECRET(self) -> str:
        return self.ytmusic.google_client_secret

    @property
    def DEFAULT_VOLUME(self) -> float:
        return self.voice.default_volume

    @property
    def MAX_QUEUE_LENGTH(self) -> int:
        return self.voice.max_queue_length

    @property
    def AUTO_DISCONNECT_TIMEOUT(self) -> int:
        return self.voice.auto_disconnect_timeout

    @property
    def YT_RADIO_ENABLED(self) -> bool:
        return self.ytmusic.radio_enabled

    @property
    def SUGGESTION_TIMEOUT(self) -> int:
        return self.ytmusic.suggestion_timeout

    @property
    def YT_PROXY(self) -> str:
        return self.audio.ytdl_proxy

    def __post_init__(self) -> None:
        """Validate required configuration settings."""
        errors: list[str] = []
        if not self.discord.bot_token:
            errors.append("DISCORD_BOT_TOKEN is required in your environment or .env file.")
        if not self.discord.client_id:
            errors.append("DISCORD_CLIENT_ID is required in your environment or .env file.")
        if self.ytmusic.auth_mode not in ("oauth", "cookie", "none"):
            errors.append("YTM_AUTH_MODE must be 'oauth', 'cookie', or 'none'.")
        if not (self.voice.min_volume <= self.voice.default_volume <= self.voice.max_volume):
            errors.append(
                f"DEFAULT_VOLUME ({self.voice.default_volume}) must be between "
                f"MIN_VOLUME ({self.voice.min_volume}) and MAX_VOLUME ({self.voice.max_volume})."
            )
        if self.voice.max_queue_length < 1:
            errors.append("MAX_QUEUE_LENGTH must be >= 1.")
        if self.ui.queue_page_size < 1:
            errors.append("QUEUE_PAGE_SIZE must be >= 1.")

        if errors:
            raise ConfigError("\n".join(errors))
