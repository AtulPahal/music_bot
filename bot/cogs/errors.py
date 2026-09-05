"""Global command error handler for hybrid and prefix commands."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bot.ui.embeds import error_embed

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class ErrorHandlerCog(commands.Cog, name="Errors"):
    """Global error handling for command failures."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Global prefix and hybrid command error dispatcher."""
        # Unwind CommandInvokeError
        if isinstance(error, commands.CommandInvokeError):
            error = error.original  # type: ignore[assignment]

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CheckFailure):
            message = str(error) or "You do not meet the requirements to run this command."
            await ctx.send(embed=error_embed(message, title="Permission Denied", config=self.bot.config))
            return

        if isinstance(error, commands.MissingRequiredArgument):
            param_name = error.param.name
            await ctx.send(
                embed=error_embed(
                    f"Missing required argument: `{param_name}`.\nUsage: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`",
                    title="Missing Argument",
                    config=self.bot.config,
                )
            )
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(embed=error_embed(str(error), title="Invalid Argument", config=self.bot.config))
            return

        if isinstance(error, commands.CommandOnCooldown):
            retry_after = round(error.retry_after, 1)
            await ctx.send(
                embed=error_embed(
                    f"This command is on cooldown. Try again in `{retry_after}s`.",
                    title="Cooldown",
                    config=self.bot.config,
                )
            )
            return

        log.exception("Unhandled command error in %s: %s", ctx.command, error)
        await ctx.send(
            embed=error_embed(
                "An unexpected error occurred while executing the command.",
                title="Execution Error",
                config=self.bot.config,
            )
        )


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(ErrorHandlerCog(bot))
