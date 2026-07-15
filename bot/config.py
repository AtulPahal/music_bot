"""Configuration loaded from environment variables with validation."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def get_clean_env(key: str, default: str = "") -> str:
    val = os.getenv(key, default)
    if not val:
        return default
    if val.strip().startswith("#"):
        return default
    if " #" in val:
        val = val.split(" #", 1)[0]
    return val.strip()


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass
class Config:
    # Discord
    DISCORD_BOT_TOKEN: str = field(default_factory=lambda: get_clean_env("DISCORD_BOT_TOKEN"))
    DISCORD_CLIENT_ID: str = field(default_factory=lambda: get_clean_env("DISCORD_CLIENT_ID"))
    DISCORD_GUILD_ID: int = field(default_factory=lambda: int(get_clean_env("DISCORD_GUILD_ID", "0")))
    DISCORD_APP_NAME: str = field(default_factory=lambda: get_clean_env("DISCORD_APP_NAME", "Music Bot"))

    # YouTube Music API (ytmusicapi)
    # OAuth credentials are optional. Without them the bot runs in
    # unauthenticated mode — search and playback still work, but
    # library/playlist/rating features are unavailable.
    YTM_AUTH_FILE: str = field(default_factory=lambda: get_clean_env("YTM_AUTH_FILE", "data/oauth.json"))
    YTM_AUTH_MODE: str = field(default_factory=lambda: get_clean_env("YTM_AUTH_MODE", "none"))
    GOOGLE_CLIENT_ID: str = field(default_factory=lambda: get_clean_env("GOOGLE_CLIENT_ID", ""))
    GOOGLE_CLIENT_SECRET: str = field(default_factory=lambda: get_clean_env("GOOGLE_CLIENT_SECRET", ""))

    # Commands
    COMMAND_PREFIX: str = field(default_factory=lambda: get_clean_env("COMMAND_PREFIX", "!"))
    OWNER_IDS: list[int] = field(default_factory=lambda: [
        int(x) for x in get_clean_env("OWNER_IDS", "").split(",") if x
    ])

    # Audio
    DEFAULT_VOLUME: float = field(default_factory=lambda: float(get_clean_env("DEFAULT_VOLUME", "0.5")))
    MAX_QUEUE_LENGTH: int = field(default_factory=lambda: int(get_clean_env("MAX_QUEUE_LENGTH", "500")))
    AUTO_DISCONNECT_TIMEOUT: int = field(default_factory=lambda: int(get_clean_env("AUTO_DISCONNECT_TIMEOUT", "300")))

    # Radio auto-suggest (when queue ends)
    YT_RADIO_ENABLED: bool = field(default_factory=lambda: get_clean_env("YT_RADIO_ENABLED", "true").lower() == "true")
    SUGGESTION_TIMEOUT: int = field(default_factory=lambda: int(get_clean_env("SUGGESTION_TIMEOUT", "30")))

    # Proxy & debug
    YT_PROXY: str = field(default_factory=lambda: get_clean_env("YT_PROXY", ""))
    LOG_LEVEL: str = field(default_factory=lambda: get_clean_env("LOG_LEVEL", "INFO"))

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        errors: list[str] = []
        if not self.DISCORD_BOT_TOKEN:
            errors.append("DISCORD_BOT_TOKEN is required")
        if not self.DISCORD_CLIENT_ID:
            errors.append("DISCORD_CLIENT_ID is required")
        if self.YTM_AUTH_MODE not in ("oauth", "cookie", "none"):
            errors.append("YTM_AUTH_MODE must be 'oauth', 'cookie', or 'none'")
        if not (0.0 <= self.DEFAULT_VOLUME <= 2.0):
            errors.append("DEFAULT_VOLUME must be between 0.0 and 2.0")
        if self.MAX_QUEUE_LENGTH < 1:
            errors.append("MAX_QUEUE_LENGTH must be >= 1")
        if errors:
            raise ConfigError("\n".join(errors))
