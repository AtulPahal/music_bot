"""Configuration loaded from environment variables with validation."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass
class Config:
    # Discord
    DISCORD_BOT_TOKEN: str = field(default_factory=lambda: os.environ["DISCORD_BOT_TOKEN"])
    DISCORD_CLIENT_ID: str = field(default_factory=lambda: os.environ["DISCORD_CLIENT_ID"])
    DISCORD_GUILD_ID: int = int(os.getenv("DISCORD_GUILD_ID") or "0")
    DISCORD_APP_NAME: str = os.getenv("DISCORD_APP_NAME", "Music Bot")

    # YouTube Music API (ytmusicapi)
    # OAuth credentials are optional. Without them the bot runs in
    # unauthenticated mode — search and playback still work, but
    # library/playlist/rating features are unavailable.
    YTM_AUTH_FILE: str = os.getenv("YTM_AUTH_FILE", "data/oauth.json")
    YTM_AUTH_MODE: str = os.getenv("YTM_AUTH_MODE") or "none"  # "oauth", "cookie", or "none"
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # Commands
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
    OWNER_IDS: list[int] = field(default_factory=lambda: [
        int(x) for x in os.getenv("OWNER_IDS", "").split(",") if x
    ])

    # Audio
    DEFAULT_VOLUME: float = float(os.getenv("DEFAULT_VOLUME") or "0.5")
    MAX_QUEUE_LENGTH: int = int(os.getenv("MAX_QUEUE_LENGTH") or "500")
    AUTO_DISCONNECT_TIMEOUT: int = int(os.getenv("AUTO_DISCONNECT_TIMEOUT") or "300")

    # Radio auto-suggest (when queue ends)
    YT_RADIO_ENABLED: bool = os.getenv("YT_RADIO_ENABLED", "true").lower() == "true"
    SUGGESTION_TIMEOUT: int = int(os.getenv("SUGGESTION_TIMEOUT") or "30")

    # Proxy & debug
    YT_PROXY: str = os.getenv("YT_PROXY", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

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
