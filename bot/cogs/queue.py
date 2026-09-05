"""Queue management commands for viewing, modifying, shuffling, and searching tracks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

from bot.audio.queue import RepeatMode, Track
from bot.ui.embeds import error_embed, queue_embed, search_embed, success_embed
from bot.ui.paginator import QueuePaginator
from bot.utils.checks import in_voice, same_voice

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class QueueCog(commands.Cog, name="Queue"):
    """Queue manipulation and search commands."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    @property
    def player(self):
        cog = self.bot.get_cog("Music")
        return cog.player if cog else None

    @commands.hybrid_command(name="queue", aliases=["q"], description="Display the current music queue.")
    async def queue(self, ctx: commands.Context) -> None:
        """View the music queue with interactive pagination."""
        if not self.player:
            await ctx.send(embed=error_embed("Player service is unavailable.", config=self.bot.config))
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("The queue is empty. Add songs with `/play`.", config=self.bot.config))
            return

        view = QueuePaginator(state.queue, config=self.bot.config)
        embed = queue_embed(state.queue, page=0, config=self.bot.config)
        message = await ctx.send(embed=embed, view=view)
        view._message = message

    @commands.hybrid_command(name="qlist", aliases=["ql"], description="Display a compact list of upcoming songs.")
    async def qlist(self, ctx: commands.Context) -> None:
        """Show a quick snapshot of upcoming tracks."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("The queue is empty.", config=self.bot.config))
            return

        cfg = self.bot.config
        embed = discord.Embed(
            title="Upcoming Queue",
            color=cfg.ui.color_queue,
        )

        current = state.queue.current
        if current:
            embed.add_field(
                name="Now Playing",
                value=f"**[{current.display}]({current.url})** `[{current.duration_str}]`",
                inline=False,
            )

        upcoming = state.queue.upcoming
        if upcoming:
            lines: list[str] = []
            for i, t in enumerate(upcoming[:15], start=1):
                pos = state.queue.position + i + 1
                req = f" (<@{t.requester_id}>)" if t.requester_id else ""
                lines.append(f"`#{pos}` **[{t.display}]({t.url})** `[{t.duration_str}]`{req}")
            if len(upcoming) > 15:
                lines.append(f"*... and {len(upcoming) - 15} more tracks.*")
            embed.add_field(
                name=f"Up Next ({len(upcoming)} tracks)",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(name="Up Next", value="No upcoming tracks in queue.", inline=False)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="history", aliases=["hist"], description="Show recently played tracks in this server.")
    async def history(self, ctx: commands.Context) -> None:
        """View previously played tracks."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        hist = state.queue.history if state else []
        if not hist:
            await ctx.send(embed=error_embed("No playback history available yet.", config=self.bot.config))
            return

        cfg = self.bot.config
        recent = hist[-15:]
        lines = [
            f"`{i}.` **[{t.display}]({t.url})** `[{t.duration_str}]`"
            for i, t in enumerate(reversed(recent), start=1)
        ]

        embed = discord.Embed(
            title="Playback History",
            description="\n".join(lines),
            color=cfg.ui.color_history,
        )
        embed.set_footer(text=f"Total played: {len(hist)} tracks")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="shuffle", description="Randomly shuffle upcoming tracks in the queue.")
    @in_voice()
    @same_voice()
    async def shuffle(self, ctx: commands.Context) -> None:
        """Shuffle all upcoming tracks."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty.", config=self.bot.config))
            return

        state.queue.shuffle()
        state.shuffle = True
        await ctx.send(embed=success_embed("Queue shuffled successfully!", title="Shuffled", config=self.bot.config))

    @commands.hybrid_command(name="loop", aliases=["repeat"], description="Toggle loop mode: off -> track -> queue -> off.")
    @in_voice()
    @same_voice()
    async def loop(self, ctx: commands.Context) -> None:
        """Cycle repeat modes."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state:
            return

        if state.repeat_mode == RepeatMode.OFF:
            state.repeat_mode = RepeatMode.TRACK
            msg = "Looping current track."
        elif state.repeat_mode == RepeatMode.TRACK:
            state.repeat_mode = RepeatMode.QUEUE
            msg = "Looping entire queue."
        else:
            state.repeat_mode = RepeatMode.OFF
            msg = "Looping disabled."

        await ctx.send(embed=success_embed(msg, title="Loop Mode", config=self.bot.config))

    @commands.hybrid_command(name="remove", aliases=["rm", "del"], description="Remove a track from the queue by position.")
    @in_voice()
    @same_voice()
    async def remove(self, ctx: commands.Context, position: int) -> None:
        """Remove a track by 1-based position."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty.", config=self.bot.config))
            return

        idx = position - 1
        removed = state.queue.remove(idx)
        if removed:
            await ctx.send(
                embed=success_embed(
                    f"Removed **[{removed.display}]({removed.url})** from position `#{position}`.",
                    title="Track Removed",
                    config=self.bot.config,
                )
            )
        else:
            await ctx.send(embed=error_embed(f"Invalid position `{position}`. Check `/queue`.", config=self.bot.config))

    @commands.hybrid_command(name="move", aliases=["mv"], description="Move a track from one queue position to another.")
    @in_voice()
    @same_voice()
    async def move(self, ctx: commands.Context, from_pos: int, to_pos: int) -> None:
        """Move a track in the queue."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty.", config=self.bot.config))
            return

        success = state.queue.move(from_pos - 1, to_pos - 1)
        if success:
            await ctx.send(
                embed=success_embed(
                    f"Moved track from position `#{from_pos}` to `#{to_pos}`.",
                    title="Track Moved",
                    config=self.bot.config,
                )
            )
        else:
            await ctx.send(embed=error_embed("Invalid positions provided. Check `/queue`.", config=self.bot.config))

    @commands.hybrid_command(name="jump", aliases=["skipto"], description="Jump directly to a specific track index in the queue.")
    @in_voice()
    @same_voice()
    async def jump(self, ctx: commands.Context, position: int) -> None:
        """Jump to a specific track in queue and begin playing."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty.", config=self.bot.config))
            return

        target = state.queue.jump_to(position - 1)
        if target:
            if state.voice_client and state.voice_client.is_playing():
                state.voice_client.stop()
            else:
                await self.player._play_next(ctx.guild.id)
            await ctx.send(
                embed=success_embed(
                    f"Jumped to position `#{position}`: **[{target.display}]({target.url})**",
                    title="Jumped",
                    config=self.bot.config,
                )
            )
        else:
            await ctx.send(embed=error_embed(f"Invalid position `#{position}`.", config=self.bot.config))

    @commands.hybrid_command(name="clear", description="Clear all upcoming tracks from the queue.")
    @in_voice()
    @same_voice()
    async def clear(self, ctx: commands.Context) -> None:
        """Clear upcoming queue."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is already empty.", config=self.bot.config))
            return

        state.queue.clear()
        await ctx.send(embed=success_embed("Cleared all upcoming tracks from queue.", title="Queue Cleared", config=self.bot.config))

    @commands.hybrid_command(name="removedupes", aliases=["dedupe"], description="Remove duplicate songs from the queue.")
    @in_voice()
    @same_voice()
    async def removedupes(self, ctx: commands.Context) -> None:
        """Deduplicate upcoming queue."""
        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty.", config=self.bot.config))
            return

        removed = state.queue.remove_duplicates()
        if removed > 0:
            await ctx.send(
                embed=success_embed(
                    f"Removed **{removed}** duplicate track{'s' if removed != 1 else ''}.",
                    title="Duplicates Removed",
                    config=self.bot.config,
                )
            )
        else:
            await ctx.send(embed=success_embed("No duplicate tracks found in queue.", config=self.bot.config))

    @commands.hybrid_command(name="search", description="Search YouTube Music and select a song from an interactive menu.")
    async def search(self, ctx: commands.Context, *, query: str) -> None:
        """Search and pick from top matching songs."""
        if not self.bot.ytmusic or not self.bot.ytmusic.available:
            await ctx.send(embed=error_embed("Search service is currently unavailable.", config=self.bot.config))
            return

        await ctx.defer()
        limit = min(25, max(1, self.bot.config.ytmusic.search_limit))
        results = await self.bot.ytmusic.search(query, filter="songs", limit=limit)

        if not results:
            await ctx.send(embed=error_embed(f"No results found for: `{query}`", config=self.bot.config))
            return

        options: list[discord.SelectOption] = []
        for i, item in enumerate(results[:25]):
            title = item.get("title", "Unknown")[:80]
            artists_raw = item.get("artists", [])
            artist_name = artists_raw[0]["name"] if artists_raw and isinstance(artists_raw[0], dict) else ""
            dur = item.get("duration", "?")
            desc = f"{artist_name} | {dur}"[:100] if artist_name else dur
            vid = item.get("videoId", "")
            options.append(
                discord.SelectOption(
                    label=f"{i + 1}. {title}",
                    description=desc,
                    value=f"{i}:{vid}",
                )
            )

        embed = search_embed(results, query, config=self.bot.config)

        class SearchSelect(discord.ui.Select):
            def __init__(self, parent_cog: QueueCog):
                super().__init__(
                    placeholder="Choose a track to play...",
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
                    await inter.followup.send(
                        embed=error_embed("Selected song has no valid video ID.", config=self.parent_cog.bot.config),
                        ephemeral=True,
                    )
                    return

                music_cog = self.parent_cog.bot.get_cog("Music")
                if music_cog:
                    await music_cog.play.callback(music_cog, ctx, query=f"https://youtu.be/{video_id}")

        view = discord.ui.View(timeout=60)
        view.add_item(SearchSelect(self))
        await ctx.send(embed=embed, view=view)


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(QueueCog(bot))
