"""Main MusicBot class — extends commands.Bot with per-guild voice state."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands

from bot.audio.queue import RepeatMode, Track
from bot.config import Config, ConfigError

log = logging.getLogger(__name__)


class GuildVoiceState:
    """Per-guild audio playback state."""

    def __init__(self) -> None:
        from bot.audio.queue import Queue

        self.voice_client: Optional[discord.VoiceClient] = None
        self.text_channel_id: int = 0
        self.current_track: Optional["Track"] = None
        self.queue: Queue = Queue()
        self.repeat_mode: "RepeatMode" = RepeatMode.OFF
        self.shuffle: bool = False
        self.volume: float = 0.5
        self._disconnect_task: Optional[asyncio.Task] = None
        self.lock = asyncio.Lock()
        self.suggested_track: Optional["Track"] = None
        self._suggest_task: Optional[asyncio.Task] = None
        self._back_requested: bool = False

    @property
    def is_playing(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_playing()

    @property
    def is_paused(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_paused()

    @property
    def is_connected(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_connected()


class MusicBot(commands.Bot):
    """Custom bot subclass holding per-guild state and services."""

    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(config.COMMAND_PREFIX),
            intents=intents,
            help_command=None,
        )

        self.config = config
        self.guild_voice_states: dict[int, GuildVoiceState] = {}
        self.ytmusic: Optional["YTMusicService"] = None  # noqa: UP037

    async def setup_hook(self) -> None:
        """Load cogs and sync slash commands."""
        from bot.cogs.music import MusicCog
        from bot.cogs.player_ui import PlayerUICog
        from bot.cogs.queue import QueueCog
        from bot.cogs.utility import UtilityCog

        await self.add_cog(MusicCog(self))
        await self.add_cog(QueueCog(self))
        await self.add_cog(PlayerUICog(self))
        await self.add_cog(UtilityCog(self))

        # Register tree error handler for auto-sync on signature mismatch
        @self.tree.error
        async def on_tree_error(
            interaction: discord.Interaction,
            error: discord.app_commands.AppCommandError,
        ) -> None:
            if isinstance(error, discord.app_commands.CommandSignatureMismatch):
                log.warning(
                    "Command signature mismatch, forcing re-sync for guild %s",
                    interaction.guild_id,
                )
                try:
                    if interaction.guild_id:
                        guild = discord.Object(id=interaction.guild_id)
                        self.tree.clear_commands(guild=guild)
                        self.tree.copy_global_to(guild=guild)
                        synced = await self.tree.sync(guild=guild)
                        log.info("Auto-synced %d commands to guild", len(synced))
                    else:
                        synced = await self.tree.sync()
                        log.info("Auto-synced %d commands globally", len(synced))
                except Exception as exc:
                    log.error("Auto-sync failed: %s", exc)

                # Tell the user to retry
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Slash commands have been refreshed. Please try `/play` again.",
                        ephemeral=True,
                    )
                return

            # Re-raise other tree errors so they still get logged
            log.error("Tree error: %s", error)

        # Always sync globally first to register commands in the global tree
        global_synced = await self.tree.sync()
        log.info("Slash commands synced globally (%d commands)", len(global_synced))

        # Then sync to guild for instant availability (overwrites stale cache)
        if self.config.DISCORD_GUILD_ID:
            guild = discord.Object(id=self.config.DISCORD_GUILD_ID)
            self.tree.clear_commands(guild=guild)
            self.tree.copy_global_to(guild=guild)
            guild_synced = await self.tree.sync(guild=guild)
            log.info(
                "Slash commands synced to guild %s (%d commands)",
                self.config.DISCORD_GUILD_ID,
                len(guild_synced),
            )

    async def on_ready(self) -> None:
        log.info("Bot logged in as %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{self.config.COMMAND_PREFIX}play | ytmusic",
            )
        )

    async def close(self) -> None:
        """Clean up voice connections on shutdown."""
        for state in self.guild_voice_states.values():
            if state.voice_client and state.voice_client.is_connected():
                await state.voice_client.disconnect(force=True)
        await super().close()
