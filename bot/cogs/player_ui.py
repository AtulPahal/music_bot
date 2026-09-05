"""Player UI commands and event listeners for voice state management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bot.ui.buttons import MusicControls
from bot.ui.embeds import error_embed, nowplaying_embed
from bot.utils.checks import in_voice, same_voice

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class PlayerUICog(commands.Cog, name="Controls"):
    """Interactive control panels and automatic voice channel cleanup."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    @property
    def player(self):
        cog = self.bot.get_cog("Music")
        return cog.player if cog else None

    @commands.hybrid_command(name="control", aliases=["panel", "c"], description="Open an interactive music control panel.")
    @in_voice()
    @same_voice()
    async def control(self, ctx: commands.Context) -> None:
        """Send an interactive control panel for current playback."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or not state.current_track:
            await ctx.send(embed=error_embed("Nothing is currently playing.", config=self.bot.config))
            return

        embed = nowplaying_embed(
            state.current_track,
            state,
            config=self.bot.config,
            position_sec=state.elapsed_seconds,
        )
        view = MusicControls(self.bot, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Auto-disconnect cleanly when all non-bot users leave the voice channel."""
        if member.bot:
            return

        guild = member.guild
        state = self.bot.guild_voice_states.get(guild.id)
        if not state or not state.voice_client or not state.voice_client.channel:
            return

        vc = state.voice_client.channel
        human_members = [m for m in vc.members if not m.bot]
        if len(human_members) == 0:
            log.info("All human users left voice channel '%s' in guild '%s'. Disconnecting.", vc.name, guild.name)
            music_cog = self.bot.get_cog("Music")
            if music_cog:
                await music_cog.player.disconnect(guild.id)
            else:
                if state.voice_client.is_connected():
                    await state.voice_client.disconnect(force=True)
                self.bot.guild_voice_states.pop(guild.id, None)


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(PlayerUICog(bot))
