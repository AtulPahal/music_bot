"""Command check decorators for voice channel validation."""

from __future__ import annotations

from discord.ext import commands


def in_voice():
    """Check that the user is in a voice channel."""

    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CheckFailure("You must be in a voice channel to use this command.")
        return True

    return commands.check(predicate)


def same_voice():
    """Check that the user is in the same voice channel as the bot."""

    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CheckFailure("You must be in a voice channel to use this command.")
        bot_vc = ctx.voice_client
        if bot_vc and bot_vc.channel.id != ctx.author.voice.channel.id:
            raise commands.CheckFailure("You must be in the same voice channel as the bot.")
        return True

    return commands.check(predicate)


def bot_has_perms(**perms):
    """Check that the bot has specific permissions in the channel."""

    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            raise commands.CheckFailure("This command can only be used in a guild.")
        bot_member = ctx.guild.me
        permissions = bot_member.permissions_in(ctx.channel)
        missing = [perm for perm, value in perms.items() if not getattr(permissions, perm, False)]
        if missing:
            raise commands.CheckFailure(
                f"I need the following permissions: {', '.join(missing)}"
            )
        return True

    return commands.check(predicate)
