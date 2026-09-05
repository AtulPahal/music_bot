"""Main MusicBot class extending commands.Bot with guild voice state tracking and lifecycle control."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

from bot.audio.player import GuildVoiceState
from bot.config import Config

if TYPE_CHECKING:
    from bot.services.ytmusic import YTMusicService

log = logging.getLogger(__name__)


class MusicBot(commands.Bot):
    """Custom bot subclass managing per-guild playback states and slash synchronization."""

    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(config.discord.command_prefix),
            intents=intents,
            help_command=None,
        )

        self.config: Config = config
        self.guild_voice_states: dict[int, GuildVoiceState] = {}
        self.ytmusic: Optional["YTMusicService"] = None

    async def setup_hook(self) -> None:
        """Load cogs and synchronize application command tree."""
        from bot.cogs.errors import ErrorHandlerCog
        from bot.cogs.music import MusicCog
        from bot.cogs.player_ui import PlayerUICog
        from bot.cogs.queue import QueueCog
        from bot.cogs.utility import UtilityCog

        await self.add_cog(MusicCog(self))
        await self.add_cog(QueueCog(self))
        await self.add_cog(PlayerUICog(self))
        await self.add_cog(UtilityCog(self))
        await self.add_cog(ErrorHandlerCog(self))

        # Command tree error handler
        @self.tree.error
        async def on_tree_error(
            interaction: discord.Interaction,
            error: discord.app_commands.AppCommandError,
        ) -> None:
            if isinstance(error, discord.app_commands.CommandSignatureMismatch):
                log.warning("Slash signature mismatch detected. Syncing commands for guild: %s", interaction.guild_id)
                try:
                    if interaction.guild_id:
                        guild_obj = discord.Object(id=interaction.guild_id)
                        self.tree.clear_commands(guild=guild_obj)
                        self.tree.copy_global_to(guild=guild_obj)
                        await self.tree.sync(guild=guild_obj)
                    else:
                        await self.tree.sync()
                except Exception as exc:
                    log.error("Tree auto-sync error: %s", exc)

                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Slash commands have been re-synchronized. Please try your command again.",
                        ephemeral=True,
                    )
                return

            log.error("Unhandled slash command tree error: %s", error)

        # Global command sync
        global_synced = await self.tree.sync()
        log.info("Registered %d slash commands globally.", len(global_synced))

        # Guild-specific instant sync if configured
        if self.config.discord.guild_id:
            guild_obj = discord.Object(id=self.config.discord.guild_id)
            self.tree.clear_commands(guild=guild_obj)
            self.tree.copy_global_to(guild=guild_obj)
            guild_synced = await self.tree.sync(guild=guild_obj)
            log.info("Registered %d slash commands for guild %s.", len(guild_synced), self.config.discord.guild_id)

    def _get_activity(self) -> discord.Activity:
        """Construct Discord activity from configuration templates."""
        raw_name = self.config.discord.activity_name.format(
            prefix=self.config.discord.command_prefix,
            app_name=self.config.discord.app_name,
        )
        act_type_str = self.config.discord.activity_type.lower()
        act_type = {
            "listening": discord.ActivityType.listening,
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "competing": discord.ActivityType.competing,
            "streaming": discord.ActivityType.streaming,
        }.get(act_type_str, discord.ActivityType.listening)

        return discord.Activity(type=act_type, name=raw_name)

    def _get_status(self) -> discord.Status:
        """Get Discord status from configuration."""
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        return status_map.get(self.config.discord.presence_status.lower(), discord.Status.online)

    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "Unknown")
        await self.change_presence(
            activity=self._get_activity(),
            status=self._get_status(),
        )

    async def close(self) -> None:
        """Clean shutdown of voice connections and services."""
        log.info("Closing bot voice connections and services...")
        for state in list(self.guild_voice_states.values()):
            if state._disconnect_task and not state._disconnect_task.done():
                state._disconnect_task.cancel()
            if state._suggest_task and not state._suggest_task.done():
                state._suggest_task.cancel()
            if state.voice_client and state.voice_client.is_connected():
                try:
                    await state.voice_client.disconnect(force=True)
                except Exception:
                    pass

        if self.ytmusic:
            await self.ytmusic.close()

        await super().close()
