"""Queue management commands: queue, move, remove, clear, shuffle, loop, search."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bot.audio.queue import RepeatMode
from bot.ui.embeds import error_embed, queue_embed, search_embed, success_embed
from bot.ui.paginator import QueuePaginator
from bot.utils.checks import in_voice, same_voice

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class QueueCog(commands.Cog):
    """Queue management commands."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    @property
    def player(self):
        from bot.cogs.music import MusicCog
        cog = self.bot.get_cog("MusicCog")
        return cog.player if cog else None

    @commands.hybrid_command(name="queue", aliases=["q"], description="Show the current music queue.")
    async def queue(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("The queue is empty. Add songs with `/play`."))
            return

        view = QueuePaginator(state.queue)
        embed = queue_embed(state.queue, page=0)
        message = await ctx.send(embed=embed, view=view)
        view._message = message

    @commands.hybrid_command(name="qlist", aliases=["ql"], description="Show a compact list of queued tracks.")
    async def qlist(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("The queue is empty. Add songs with `/play`."))
            return

        tracks = state.queue.all_tracks()
        pos = state.queue.position
        current = state.queue.current

        embed = discord.Embed(
            title="Queue",
            color=discord.Color.blurple(),
        )

        # Show current track
        if current:
            embed.add_field(
                name="Now Playing",
                value=f"**{current.display}** [`{current.duration_str}`]",
                inline=False,
            )

        # Show upcoming tracks
        upcoming = state.queue.upcoming
        if upcoming:
            lines = []
            for i, t in enumerate(upcoming[:15], 1):
                req = f"<@{t.requester_id}>" if t.requester_id else ""
                lines.append(f"`#{pos + i}` {t.display} [`{t.duration_str}`] {req}")
            if len(upcoming) > 15:
                lines.append(f"*... and {len(upcoming) - 15} more*")
            embed.add_field(
                name=f"Up Next ({len(upcoming)} track{'s' if len(upcoming) != 1 else ''})",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.set_footer(text="Queue is empty after this track.")

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="history", aliases=["hist"], description="Show recently played tracks.")
    async def history(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state:
            await ctx.send(embed=error_embed("No active session."))
            return

        hist = state.queue.history
        if not hist:
            await ctx.send(embed=error_embed("No playback history yet."))
            return

        # Show last 15
        recent = hist[-15:]
        lines = []
        for i, t in enumerate(reversed(recent), 1):
            lines.append(f"`{i}.` **{t.display}** [`{t.duration_str}`]")

        embed = discord.Embed(
            title="Playback History",
            description="\n".join(lines),
            color=discord.Color.dark_magenta(),
        )
        embed.set_footer(text=f"Total: {len(hist)} track{'s' if len(hist) != 1 else ''} played")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="shuffle", description="Shuffle the queue.")
    @in_voice()
    @same_voice()
    async def shuffle(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty."))
            return

        state.queue.shuffle()
        state.shuffle = True
        await ctx.send(embed=success_embed("Queue shuffled!"))

    @commands.hybrid_command(name="loop", aliases=["repeat"], description="Toggle loop mode: off → track → queue → off.")
    @in_voice()
    @same_voice()
    async def loop(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state:
            await ctx.send(embed=error_embed("No active session."))
            return

        if state.repeat_mode == RepeatMode.OFF:
            state.repeat_mode = RepeatMode.TRACK
            await ctx.send(embed=success_embed("Looping current track."))
        elif state.repeat_mode == RepeatMode.TRACK:
            state.repeat_mode = RepeatMode.QUEUE
            await ctx.send(embed=success_embed("Looping entire queue."))
        else:
            state.repeat_mode = RepeatMode.OFF
            await ctx.send(embed=success_embed("Looping disabled."))

    @commands.hybrid_command(name="remove", aliases=["rm"], description="Remove a track from the queue by position.")
    @in_voice()
    @same_voice()
    async def remove(self, ctx: commands.Context, position: int) -> None:
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty."))
            return

        idx = position - 1  # Convert from 1-based to 0-based
        removed = state.queue.remove(idx)
        if removed:
            await ctx.send(
                embed=success_embed(f"Removed **{removed.display}** from position {position}.")
            )
        else:
            await ctx.send(embed=error_embed(f"Invalid position {position}. Use `/queue` to see positions."))

    @commands.hybrid_command(name="move", description="Move a track from one position to another.")
    @in_voice()
    @same_voice()
    async def move(self, ctx: commands.Context, from_pos: int, to_pos: int) -> None:
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty."))
            return

        success = state.queue.move(from_pos - 1, to_pos - 1)
        if success:
            await ctx.send(embed=success_embed(f"Moved track from position {from_pos} to {to_pos}."))
        else:
            await ctx.send(embed=error_embed("Invalid positions. Use `/queue` to see positions."))

    @commands.hybrid_command(name="clear", description="Clear all upcoming tracks from the queue.")
    @in_voice()
    @same_voice()
    async def clear(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id) if self.player else None
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is already empty."))
            return

        state.queue.clear()
        await ctx.send(embed=success_embed("Cleared all upcoming tracks."))

    @commands.hybrid_command(name="search", description="Search YouTube Music and pick a result to play.")
    async def search(self, ctx: commands.Context, *, query: str) -> None:
        """Search YouTube Music and present a selection."""
        if not self.bot.ytmusic or not self.bot.ytmusic.available:
            await ctx.send(embed=error_embed("YouTube Music search is unavailable."))
            return

        await ctx.defer()
        results = await self.bot.ytmusic.search(query, filter="songs", limit=5)

        if not results:
            await ctx.send(embed=error_embed(f"No results for: `{query}`"))
            return

        # Build a select menu
        options = []
        for i, r in enumerate(results):
            title = r.get("title", "Unknown")[:80]
            artists_raw = r.get("artists", [])
            artist = artists_raw[0]["name"] if artists_raw else ""
            duration = r.get("duration", "?")
            desc = f"{artist} • {duration}"[:100]
            video_id = r.get("videoId", "")
            options.append(
                discord.SelectOption(
                    label=title,
                    description=desc,
                    value=f"{i}:{video_id}",
                )
            )

        embed = search_embed(results, query)

        class SearchSelect(discord.ui.Select):
            def __init__(self, parent_cog):
                super().__init__(
                    placeholder="Choose a result...",
                    min_values=1,
                    max_values=1,
                    options=options,
                )
                self.parent_cog = parent_cog

            async def callback(self, inter: discord.Interaction) -> None:
                await inter.response.defer()
                parts = self.values[0].split(":", 1)
                idx = int(parts[0])
                chosen = results[idx]
                video_id = chosen.get("videoId", "")

                if not video_id:
                    await inter.followup.send(embed=error_embed("Invalid selection."), ephemeral=True)
                    return

                # Create a temporary context-like command
                from bot.cogs.music import MusicCog
                cog: MusicCog = self.parent_cog.bot.get_cog("MusicCog")
                if not cog:
                    return

                # Use the play command logic
                await cog.play.callback(cog, ctx, query=f"https://youtu.be/{video_id}")
                await inter.followup.send(embed=success_embed(f"Added **{chosen.get('title', '')}**!"), ephemeral=True)

        view = discord.ui.View(timeout=60)
        view.add_item(SearchSelect(self))

        await ctx.send(embed=embed, view=view)


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(QueueCog(bot))
