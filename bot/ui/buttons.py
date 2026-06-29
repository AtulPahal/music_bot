"""Interactive music control buttons for nowplaying/control embed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord

if TYPE_CHECKING:
    from bot.bot import MusicBot


class MusicControls(discord.ui.View):
    """Persistent music control buttons (pause/resume, skip, stop, loop, shuffle)."""

    def __init__(self, bot: "MusicBot", guild_id: int) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id

    def _get_state(self):
        return self.bot.guild_voice_states.get(self.guild_id)

    @discord.ui.button(label="Play/Pause", style=discord.ButtonStyle.primary, custom_id="music_pause")
    async def toggle_pause(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        state = self._get_state()
        if not state or not state.voice_client:
            return await interaction.response.send_message("Not connected to voice.", ephemeral=True)

        if state.is_playing:
            state.voice_client.pause()
            button.label = "Resume"
            await interaction.response.edit_message(view=self)
        elif state.is_paused:
            state.voice_client.resume()
            button.label = "Play/Pause"
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, custom_id="music_skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        state = self._get_state()
        if not state or not state.is_playing:
            return await interaction.response.send_message("Nothing to skip.", ephemeral=True)

        state.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, custom_id="music_stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        state = self._get_state()
        if not state or not state.is_playing:
            return await interaction.response.send_message("Nothing to stop.", ephemeral=True)

        state.queue.clear()
        state.voice_client.stop()
        state.current_track = None
        await interaction.response.send_message("Stopped and cleared queue.", ephemeral=True)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary, custom_id="music_loop")
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        from bot.audio.queue import RepeatMode

        state = self._get_state()
        if not state:
            return await interaction.response.send_message("No active session.", ephemeral=True)

        if state.repeat_mode == RepeatMode.OFF:
            state.repeat_mode = RepeatMode.TRACK
            button.label = "Loop-Track"
            await interaction.response.edit_message(view=self)
        elif state.repeat_mode == RepeatMode.TRACK:
            state.repeat_mode = RepeatMode.QUEUE
            button.label = "Loop-Queue"
            await interaction.response.edit_message(view=self)
        else:
            state.repeat_mode = RepeatMode.OFF
            button.label = "Loop"
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Shuffle", style=discord.ButtonStyle.secondary, custom_id="music_shuffle")
    async def toggle_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        state = self._get_state()
        if not state or not state.queue:
            return await interaction.response.send_message("No active session.", ephemeral=True)

        state.shuffle = not state.shuffle
        if state.shuffle:
            state.queue.shuffle()
        button.style = discord.ButtonStyle.primary if state.shuffle else discord.ButtonStyle.secondary
        button.label = "Shuffle-On" if state.shuffle else "Shuffle"
        await interaction.response.edit_message(view=self)
