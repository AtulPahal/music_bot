"""Command check decorators for voice channel connection and permission validation."""

from __future__ import annotations

from typing import Callable, TypeVar

import discord
from discord.ext import commands

T = TypeVar("T", bound=Callable)


def in_voice() -> Callable[[T], T]:
    """Check that the command author is currently in a voice channel."""

    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CheckFailure("You must be connected to a voice channel to use this command.")
        return True

    return commands.check(predicate)


def same_voice() -> Callable[[T], T]:
    """Check that the command author is in the same voice channel as the bot."""

    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CheckFailure("You must be in a voice channel to use this command.")

        voice_client: discord.VoiceClient | None = ctx.voice_client  # type: ignore[assignment]
        if voice_client and voice_client.channel:
            if voice_client.channel.id != ctx.author.voice.channel.id:
                raise commands.CheckFailure(
                    f"You must be in the same voice channel as the bot ({voice_client.channel.mention})."
                )
        return True

    return commands.check(predicate)


def bot_has_voice_perms() -> Callable[[T], T]:
    """Check that the bot has Connect and Speak permissions in the target channel."""

    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild or not ctx.guild.me:
            raise commands.CheckFailure("This command can only be used in a server.")

        channel = None
        if ctx.author.voice and ctx.author.voice.channel:
            channel = ctx.author.voice.channel
        elif ctx.voice_client and ctx.voice_client.channel:
            channel = ctx.voice_client.channel

        if channel:
            perms = channel.permissions_for(ctx.guild.me)
            missing = []
            if not perms.connect:
                missing.append("Connect")
            if not perms.speak:
                missing.append("Speak")
            if missing:
                raise commands.CheckFailure(
                    f"I am missing the following permissions in {channel.mention}: **{' and '.join(missing)}**."
                )
        return True

    return commands.check(predicate)
