"""Utility, connection management, diagnostic, and dynamic help commands."""

from __future__ import annotations

import logging
import platform
import sys
import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bot.ui.embeds import error_embed, info_embed, success_embed

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class UtilityCog(commands.Cog, name="Utility"):
    """Connection management, diagnostics, and bot information."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot
        self._start_time = time.time()

    @property
    def player(self):
        cog = self.bot.get_cog("Music")
        return cog.player if cog else None

    @commands.hybrid_command(name="join", aliases=["connect", "j"], description="Connect the bot to your voice channel.")
    async def join(self, ctx: commands.Context) -> None:
        """Connect to voice channel."""
        if not self.player:
            await ctx.send(embed=error_embed("Music player unavailable.", config=self.bot.config))
            return

        success, err = await self.player.join(ctx)
        if success:
            channel = ctx.author.voice.channel
            await ctx.send(embed=success_embed(f"Connected to {channel.mention}.", config=self.bot.config))
        else:
            await ctx.send(embed=error_embed(err, config=self.bot.config))

    @commands.hybrid_command(name="disconnect", aliases=["dc", "leave"], description="Disconnect the bot from voice.")
    async def disconnect(self, ctx: commands.Context) -> None:
        """Disconnect and clear voice state."""
        if not ctx.voice_client:
            await ctx.send(embed=error_embed("I am not connected to a voice channel.", config=self.bot.config))
            return

        channel_name = ctx.voice_client.channel.name if ctx.voice_client.channel else "Voice"
        if self.player:
            await self.player.disconnect(ctx.guild.id)
        else:
            await ctx.voice_client.disconnect(force=True)
            self.bot.guild_voice_states.pop(ctx.guild.id, None)

        await ctx.send(embed=success_embed(f"Disconnected from {channel_name}.", config=self.bot.config))

    @commands.hybrid_command(name="ping", description="Check bot latency and response time.")
    async def ping(self, ctx: commands.Context) -> None:
        """Check websocket latency."""
        latency_ms = round(self.bot.latency * 1000)
        cfg = self.bot.config
        embed = discord.Embed(
            title="Pong!",
            description=f"Gateway Latency: **{latency_ms}ms**",
            color=cfg.ui.color_success if latency_ms < 150 else cfg.ui.color_warning,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="info", aliases=["botinfo", "stats", "about"], description="Display bot runtime statistics.")
    async def info(self, ctx: commands.Context) -> None:
        """Show bot stats and system information."""
        cfg = self.bot.config
        uptime_sec = int(time.time() - self._start_time)
        m, s = divmod(uptime_sec, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        uptime_str = f"{d}d {h}h {m}m {s}s" if d else f"{h}h {m}m {s}s"

        embed = discord.Embed(
            title=f"{cfg.discord.app_name} Information",
            color=cfg.ui.color_primary,
        )
        embed.add_field(name="Servers", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="Latency", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="Python", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="discord.py", value=f"`{discord.__version__}`", inline=True)
        embed.add_field(name="Prefix", value=f"`{cfg.discord.command_prefix}`", inline=True)

        if cfg.ui.footer_text:
            embed.set_footer(text=cfg.ui.footer_text)

        await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.hybrid_command(name="sync", description="Synchronize application slash commands with Discord (Owner Only).")
    async def sync(self, ctx: commands.Context, reset_global: bool = False) -> None:
        """Force re-synchronize slash commands with Discord."""
        await ctx.defer(ephemeral=True)
        try:
            if reset_global:
                self.bot.tree.clear_commands(guild=None)
                await self.bot.tree.sync()
                log.info("Reset all global slash commands")

            global_synced = await self.bot.tree.sync()
            count = len(global_synced)

            if self.bot.config.discord.guild_id:
                guild = discord.Object(id=self.bot.config.discord.guild_id)
                self.bot.tree.clear_commands(guild=guild)
                self.bot.tree.copy_global_to(guild=guild)
                guild_synced = await self.bot.tree.sync(guild=guild)
                count = len(guild_synced)

            msg = f"Successfully synced {count} slash command{'s' if count != 1 else ''}."
            if reset_global:
                msg += "\nGlobal command cache cleared."
            await ctx.send(embed=success_embed(msg, title="Commands Synced", config=self.bot.config))
        except Exception as e:
            log.error("Sync command failed: %s", e)
            await ctx.send(embed=error_embed(f"Failed to sync slash commands: {e}", config=self.bot.config))

    @commands.hybrid_command(name="help", description="Show full list of available commands.")
    async def help(self, ctx: commands.Context, command_name: str | None = None) -> None:
        """Dynamic help menu reading directly from loaded cogs and registered commands."""
        cfg = self.bot.config
        prefix = cfg.discord.command_prefix

        # Specific command help
        if command_name:
            cmd = self.bot.get_command(command_name)
            if not cmd:
                await ctx.send(
                    embed=error_embed(f"Command `{command_name}` was not found.", config=self.bot.config)
                )
                return

            embed = discord.Embed(
                title=f"Command: {prefix}{cmd.qualified_name}",
                description=cmd.help or cmd.description or "No description provided.",
                color=cfg.ui.color_primary,
            )
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(f"`{a}`" for a in cmd.aliases), inline=False)
            usage = f"/{cmd.qualified_name} {cmd.signature}".strip()
            embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
            await ctx.send(embed=embed)
            return

        # Overall help menu dynamically grouped by Cog
        embed = discord.Embed(
            title=f"{cfg.discord.app_name} Commands",
            description=f"Use `/{command_name}` or `{prefix}{command_name}` to run commands.",
            color=cfg.ui.color_primary,
        )

        for cog_name, cog in self.bot.cogs.items():
            cmd_list = []
            for cmd in cog.get_commands():
                if cmd.hidden:
                    continue
                cmd_desc = cmd.description or cmd.help or "No description."
                cmd_list.append(f"`/{cmd.name}` - {cmd_desc}")

            if cmd_list:
                embed.add_field(
                    name=f"{cog_name}",
                    value="\n".join(cmd_list),
                    inline=False,
                )

        footer = f"Type {prefix}help <command> for command details."
        if cfg.ui.footer_text:
            footer = f"{footer} | {cfg.ui.footer_text}"
        embed.set_footer(text=footer)

        await ctx.send(embed=embed)


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(UtilityCog(bot))
