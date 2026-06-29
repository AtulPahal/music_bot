"""Utility commands: join, disconnect, ping, help, owner-only."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bot.ui.embeds import error_embed, success_embed

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class UtilityCog(commands.Cog):
    """Bot utility and voice connection management."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    @property
    def player(self):
        return self.bot.get_cog("MusicCog").player if self.bot.get_cog("MusicCog") else None

    # --- Join / Disconnect ---

    @commands.hybrid_command(name="join", description="Join your voice channel.")
    async def join(self, ctx: commands.Context) -> None:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=error_embed("You must be in a voice channel first."))
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client:
            if ctx.voice_client.channel.id == channel.id:
                await ctx.send(embed=success_embed(f"Already connected to {channel.mention}."))
                return
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

        state = self.bot.guild_voice_states.get(ctx.guild.id)
        if state:
            state.text_channel_id = ctx.channel.id

        await ctx.send(embed=success_embed(f"Joined {channel.mention}!"))

    @commands.hybrid_command(name="disconnect", aliases=["dc", "leave"], description="Disconnect the bot from voice.")
    async def disconnect(self, ctx: commands.Context) -> None:
        if not ctx.voice_client:
            await ctx.send(embed=error_embed("I'm not connected to a voice channel."))
            return

        channel_name = ctx.voice_client.channel.name
        await ctx.voice_client.disconnect(force=True)

        # Clean up state
        self.bot.guild_voice_states.pop(ctx.guild.id, None)

        await ctx.send(embed=success_embed(f"Disconnected from {channel_name}."))

    # --- Ping ---

    @commands.hybrid_command(name="ping", description="Check the bot's latency.")
    async def ping(self, ctx: commands.Context) -> None:
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="Pong!",
            description=f"Latency: **{latency}ms**",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    # --- Sync ---

    @commands.is_owner()
    @commands.hybrid_command(name="sync", description="Force re-sync slash commands (owner only).")
    async def sync(self, ctx: commands.Context, reset_global: bool = False) -> None:
        """Force re-sync slash commands with Discord.

        Run this if slash commands show the wrong parameters or "command signature mismatch".

        Parameters
        -----------
        reset_global: If True, clears ALL global commands first (fixes stale global cache).
        """
        await ctx.defer(ephemeral=True)
        try:
            # Optionally wipe global commands first
            if reset_global:
                self.bot.tree.clear_commands(guild=None)
                await self.bot.tree.sync()
                log.info("Cleared all global slash commands")

            # Re-sync globally first
            global_synced = await self.bot.tree.sync()

            # Then sync to guild
            if self.bot.config.DISCORD_GUILD_ID:
                guild = discord.Object(id=self.bot.config.DISCORD_GUILD_ID)
                self.bot.tree.clear_commands(guild=guild)
                self.bot.tree.copy_global_to(guild=guild)
                guild_synced = await self.bot.tree.sync(guild=guild)
                total = len(guild_synced)
            else:
                total = len(global_synced)

            msg = f"Synced **{total}** slash command{'s' if total != 1 else ''}."
            if reset_global:
                msg += "\n✅ Global commands reset."
            msg += "\nChanges may take a few seconds to appear."

            await ctx.send(embed=success_embed(msg))
        except Exception as e:
            await ctx.send(embed=error_embed(f"Sync failed: {e}"))

    # --- Help ---

    @commands.hybrid_command(name="help", description="Show available commands.")
    async def help(self, ctx: commands.Context) -> None:
        embed = discord.Embed(
            title=f"{self.bot.config.DISCORD_APP_NAME} Commands",
            description="Here are the available commands. Use `/` for slash commands.",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Music",
            value=(
                "`/play <song/url>` - Play a song or add to queue\n"
                "`/addq <song/url>` - Add to queue (starts if idle)\n"
                "`/playskip <song>` - Play immediately, skipping current\n"
                "`/playtop <song>` - Add to top of queue\n"
                "`/back` - Go back to previous track\n"
                "`/pause` - Pause playback\n"
                "`/resume` - Resume playback\n"
                "`/skip` / `next` - Skip current track\n"
                "`/stop` - Stop and clear queue\n"
                "`/nowplaying` - Show current track\n"
                "`/volume <0-200>` - Set volume"
            ),
            inline=False,
        )

        embed.add_field(
            name="Queue",
            value=(
                "`/queue` / `qlist` - Show the queue\n"
                "`/history` - Show recently played\n"
                "`/search <query>` - Search and pick a result\n"
                "`/shuffle` - Shuffle the queue\n"
                "`/loop` - Toggle loop mode\n"
                "`/remove <position>` - Remove a track\n"
                "`/move <from> <to>` - Move a track\n"
                "`/clear` - Clear the queue"
            ),
            inline=False,
        )

        embed.add_field(
            name="Utility",
            value=(
                "`/join` - Join your voice channel\n"
                "`/disconnect` - Disconnect from voice\n"
                "`/ping` - Check latency\n"
                "`/sync` - Re-sync slash commands (owner only)\n"
                "`/help` - Show this message"
            ),
            inline=False,
        )

        await ctx.send(embed=embed)


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(UtilityCog(bot))
