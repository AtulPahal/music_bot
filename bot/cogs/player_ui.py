"""Player UI commands: interactive control buttons and nowplaying enhancements."""

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


class PlayerUICog(commands.Cog):
    """Interactive control panels and UI enhancements."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    @property
    def player(self):
        from bot.cogs.music import MusicCog
        cog = self.bot.get_cog("MusicCog")
        return cog.player if cog else None

    @commands.hybrid_command(name="control", description="Open an interactive music control panel.")
    @in_voice()
    @same_voice()
    async def control(self, ctx: commands.Context) -> None:
        """Send an embed with interactive music control buttons."""
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state or not state.current_track:
            await ctx.send(embed=error_embed("Nothing is currently playing."))
            return

        track = state.current_track
        embed = nowplaying_embed(track, state)

        view = MusicControls(self.bot, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Auto-disconnect when everyone leaves the voice channel."""
        if member.bot:
            return

        guild = member.guild
        state = self.bot.guild_voice_states.get(guild.id)
        if not state or not state.voice_client:
            return

        # Check if bot is in a voice channel and all non-bot members have left
        vc = state.voice_client.channel
        if vc and len([m for m in vc.members if not m.bot]) == 0:
            log.info("All users left %s in %s, disconnecting.", vc.name, guild.name)
            if state.voice_client and state.voice_client.is_connected():
                await state.voice_client.disconnect(force=True)
            self.bot.guild_voice_states.pop(guild.id, None)


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(PlayerUICog(bot))
