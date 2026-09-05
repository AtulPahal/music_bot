"""Interactive music control buttons for Discord playback with clear text labels."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import discord

from bot.audio.queue import RepeatMode
from bot.ui.embeds import error_embed

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class MusicControls(discord.ui.View):
    """Interactive control view for pause/resume, skip, back, stop, loop, and shuffle."""

    def __init__(self, bot: "MusicBot", guild_id: int) -> None:
        timeout = bot.config.ui.button_timeout
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id
        self._sync_button_labels()

    def _get_state(self):
        return self.bot.guild_voice_states.get(self.guild_id)

    def _sync_button_labels(self) -> None:
        """Update button labels based on current playback state."""
        state = self._get_state()

        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
            if item.custom_id == "ctrl_play_pause":
                if state and state.is_paused:
                    item.label = "Resume"
                    item.style = discord.ButtonStyle.success
                else:
                    item.label = "Pause"
                    item.style = discord.ButtonStyle.primary
            elif item.custom_id == "ctrl_loop":
                if state and state.repeat_mode == RepeatMode.TRACK:
                    item.label = "Loop: Track"
                    item.style = discord.ButtonStyle.success
                elif state and state.repeat_mode == RepeatMode.QUEUE:
                    item.label = "Loop: Queue"
                    item.style = discord.ButtonStyle.success
                else:
                    item.label = "Loop: Off"
                    item.style = discord.ButtonStyle.secondary
            elif item.custom_id == "ctrl_shuffle":
                is_shuffled = bool(state and getattr(state, "shuffle", False))
                item.label = "Shuffle: On" if is_shuffled else "Shuffle: Off"
                item.style = discord.ButtonStyle.primary if is_shuffled else discord.ButtonStyle.secondary

    async def _check_permissions(self, interaction: discord.Interaction) -> bool:
        """Ensure the interaction user is in the same voice channel as the bot."""
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Command must be run in a server.", config=self.bot.config),
                ephemeral=True,
            )
            return False

        user_voice = interaction.user.voice
        if not user_voice or not user_voice.channel:
            await interaction.response.send_message(
                embed=error_embed("You must be connected to a voice channel to use music controls.", config=self.bot.config),
                ephemeral=True,
            )
            return False

        state = self._get_state()
        if not state or not state.voice_client or not state.voice_client.channel:
            await interaction.response.send_message(
                embed=error_embed("The bot is not currently active in a voice channel.", config=self.bot.config),
                ephemeral=True,
            )
            return False

        if state.voice_client.channel.id != user_voice.channel.id:
            await interaction.response.send_message(
                embed=error_embed(
                    f"You must be in the same voice channel as the bot ({state.voice_client.channel.mention}).",
                    config=self.bot.config,
                ),
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, custom_id="ctrl_back", row=0)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._check_permissions(interaction):
            return

        music_cog = self.bot.get_cog("Music")
        if not music_cog:
            await interaction.response.send_message("Music service unavailable.", ephemeral=True)
            return

        prev = await music_cog.player.back(self.guild_id)
        if prev:
            self._sync_button_labels()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(
                embed=error_embed("No previous track in history.", config=self.bot.config),
                ephemeral=True,
            )

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary, custom_id="ctrl_play_pause", row=0)
    async def play_pause_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._check_permissions(interaction):
            return

        state = self._get_state()
        if not state or not state.voice_client:
            await interaction.response.send_message("No active playback.", ephemeral=True)
            return

        if state.is_playing:
            state.voice_client.pause()
        elif state.is_paused:
            state.voice_client.resume()

        self._sync_button_labels()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, custom_id="ctrl_skip", row=0)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._check_permissions(interaction):
            return

        state = self._get_state()
        if not state or not state.is_playing:
            await interaction.response.send_message(
                embed=error_embed("Nothing is currently playing to skip.", config=self.bot.config),
                ephemeral=True,
            )
            return

        state.voice_client.stop()
        self._sync_button_labels()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, custom_id="ctrl_stop", row=0)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._check_permissions(interaction):
            return

        music_cog = self.bot.get_cog("Music")
        if music_cog:
            await music_cog.player.stop(self.guild_id)

        self._sync_button_labels()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Loop: Off", style=discord.ButtonStyle.secondary, custom_id="ctrl_loop", row=1)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._check_permissions(interaction):
            return

        state = self._get_state()
        if not state:
            return

        if state.repeat_mode == RepeatMode.OFF:
            state.repeat_mode = RepeatMode.TRACK
        elif state.repeat_mode == RepeatMode.TRACK:
            state.repeat_mode = RepeatMode.QUEUE
        else:
            state.repeat_mode = RepeatMode.OFF

        self._sync_button_labels()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Shuffle: Off", style=discord.ButtonStyle.secondary, custom_id="ctrl_shuffle", row=1)
    async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._check_permissions(interaction):
            return

        state = self._get_state()
        if not state or state.queue.is_empty:
            await interaction.response.send_message(
                embed=error_embed("Queue is empty.", config=self.bot.config),
                ephemeral=True,
            )
            return

        state.shuffle = not getattr(state, "shuffle", False)
        if state.shuffle:
            state.queue.shuffle()

        self._sync_button_labels()
        await interaction.response.edit_message(view=self)
