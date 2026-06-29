"""Core music commands: play, pause, resume, skip, stop, nowplaying, volume."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

from bot.audio.player import Player
from bot.audio.queue import Track
from bot.ui.embeds import error_embed, nowplaying_embed, search_embed, success_embed
from bot.utils.checks import in_voice, same_voice
from bot.utils.url_helpers import extract_video_id

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class MusicCog(commands.Cog):
    """Core music playback commands."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot
        self.player = Player(bot)

    # --- Helper: resolve a query to a Track ---

    async def _resolve_query(self, query: str, requester_id: int) -> Optional[Track]:
        video_id = extract_video_id(query)

        if video_id:
            from bot.audio.source import extract_info

            info = await extract_info(video_id, proxy=self.bot.config.YT_PROXY)
            if not info:
                return None

            title = info.get("title", "Unknown")
            duration = info.get("duration", 0) or 0
            thumbnail = info.get("thumbnail", "")
            uploader = info.get("uploader", "")
            webpage_url = info.get("webpage_url", "")

            track = Track(
                video_id=video_id,
                title=title,
                artists=[uploader] if uploader else [],
                duration=duration or 0,
                thumbnail_url=thumbnail or "",
                requester_id=requester_id,
                source_url=webpage_url or query,
            )
            return track

        # Otherwise, search YouTube Music
        if not self.bot.ytmusic or not self.bot.ytmusic.available:
            return None

        results = await self.bot.ytmusic.search(query, filter="songs", limit=1)
        if not results:
            return None

        best = results[0]
        vid = best.get("videoId")
        if not vid:
            return None

        title = best.get("title", "Unknown")
        artists_raw = best.get("artists", [])
        artists = [a["name"] for a in artists_raw if isinstance(a, dict) and "name" in a]

        duration_sec = best.get("duration_seconds", 0)
        if not duration_sec:
            raw_dur = best.get("duration", "0:00")
            parts = list(map(int, raw_dur.split(":")))
            duration_sec = (parts[0] * 60 + parts[1]) if len(parts) == 2 else parts[0]

        thumbnails = best.get("thumbnails", [])
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else ""

        return Track(
            video_id=vid,
            title=title,
            artists=artists,
            duration=duration_sec,
            thumbnail_url=thumbnail_url,
            requester_id=requester_id,
        )

    # --- Commands ---

    @commands.hybrid_command(name="play", aliases=["p"], description="Play a song or add it to the queue.")
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Search and play a song, or add it to the queue if something is already playing."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=error_embed("You must be in a voice channel first."))
            return

        # Join or move to the user's channel
        success = await self.player.join(ctx)
        if not success:
            await ctx.send(embed=error_embed("Could not join your voice channel. Check permissions."))
            return

        # Resolve the query
        await ctx.defer()
        track = await self._resolve_query(query, ctx.author.id)
        if not track:
            await ctx.send(embed=error_embed(f"Could not find anything for: `{query}`"))
            return

        # Add to queue / play
        guild_id = ctx.guild.id
        state = self.player.get_state(guild_id)
        was_playing = state.is_playing or state.is_paused

        if was_playing:
            state.queue.add(track)
            embed = success_embed(
                f"Added to queue: **[{track.display}]({track.url})**\nPosition: #{state.queue.length}",
                title="Added to Queue",
            )
        else:
            state.queue.add(track)
            await self.player._play_next(guild_id)
            embed = nowplaying_embed(track, state)

        if track.thumbnail_url:
            embed.set_thumbnail(url=track.thumbnail_url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="playskip", aliases=["ps"], description="Play a song immediately, skipping the current track.")
    async def playskip(self, ctx: commands.Context, *, query: str) -> None:
        """Play a song immediately, skipping the current track."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=error_embed("You must be in a voice channel first."))
            return

        success, err = await self.player.join(ctx)
        if not success:
            await ctx.send(embed=error_embed(err))
            return

        await ctx.defer()
        track = await self._resolve_query(query, ctx.author.id)
        if not track:
            await ctx.send(embed=error_embed(f"Could not find: `{query}`"))
            return

        guild_id = ctx.guild.id
        state = self.player.get_state(guild_id)

        # Add to front and skip current
        state.queue.add(track, at_front=True)
        if state.is_playing:
            state.voice_client.stop()  # triggers play_next

        embed = success_embed(
            f"Playing now: **[{track.display}]({track.url})**",
            title="Skipped to",
        )
        if track.thumbnail_url:
            embed.set_thumbnail(url=track.thumbnail_url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="playtop", aliases=["pt"], description="Add a song to the top of the queue.")
    async def playtop(self, ctx: commands.Context, *, query: str) -> None:
        """Search and add a song to the front of the queue."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=error_embed("You must be in a voice channel first."))
            return

        success, err = await self.player.join(ctx)
        if not success:
            await ctx.send(embed=error_embed(err))
            return

        await ctx.defer()
        track = await self._resolve_query(query, ctx.author.id)
        if not track:
            await ctx.send(embed=error_embed(f"Could not find: `{query}`"))
            return

        state = self.player.get_state(ctx.guild.id)
        state.queue.add(track, at_front=True)

        embed = success_embed(
            f"Added to top of queue: **[{track.display}]({track.url})**",
            title="Play Next",
        )
        if track.thumbnail_url:
            embed.set_thumbnail(url=track.thumbnail_url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause", description="Pause the current track.")
    @in_voice()
    @same_voice()
    async def pause(self, ctx: commands.Context) -> None:
        success = await self.player.pause(ctx.guild.id)
        if success:
            await ctx.send(embed=success_embed("Playback paused."))
        else:
            await ctx.send(embed=error_embed("Nothing is playing."))

    @commands.hybrid_command(name="resume", description="Resume playback.")
    @in_voice()
    @same_voice()
    async def resume(self, ctx: commands.Context) -> None:
        success = await self.player.resume(ctx.guild.id)
        if success:
            await ctx.send(embed=success_embed("Playback resumed."))
        else:
            await ctx.send(embed=error_embed("Nothing is paused."))

    @commands.hybrid_command(name="back", aliases=["prev"], description="Go back to the previous track.")
    @in_voice()
    @same_voice()
    async def back(self, ctx: commands.Context) -> None:
        """Play the previous track from history."""
        state = self.player.get_state(ctx.guild.id)
        prev = await self.player.back(ctx.guild.id)
        if prev is None:
            await ctx.send(embed=error_embed("No previous track to go back to."))
            return

        # Wait briefly for playback to start
        await asyncio.sleep(0.3)

        now_playing = state.current_track
        if now_playing:
            embed = nowplaying_embed(now_playing, state)
            embed.description = "Going back to previous track"
            if now_playing.thumbnail_url:
                embed.set_thumbnail(url=now_playing.thumbnail_url)
            await ctx.send(embed=embed)
        else:
            embed = success_embed(
                f"Going back to **[{prev.display}]({prev.url})**",
                title="Previous Track",
            )
            if prev.thumbnail_url:
                embed.set_thumbnail(url=prev.thumbnail_url)
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="addq", aliases=["queueadd"], description="Add a song to the queue.")
    async def addq(self, ctx: commands.Context, *, query: str) -> None:
        """Add a track to the queue without changing what's playing."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(embed=error_embed("You must be in a voice channel first."))
            return

        success, err = await self.player.join(ctx)
        if not success:
            await ctx.send(embed=error_embed(err))
            return

        await ctx.defer()
        track = await self._resolve_query(query, ctx.author.id)
        if not track:
            await ctx.send(embed=error_embed(f"Could not find: `{query}`"))
            return

        guild_id = ctx.guild.id
        state = self.player.get_state(guild_id)
        was_playing = state.is_playing or state.is_paused

        state.queue.add(track)

        if not was_playing:
            # Nothing was playing, start playback
            await self.player._play_next(guild_id)
            embed = nowplaying_embed(track, state)
        else:
            embed = success_embed(
                f"Added to queue: **[{track.display}]({track.url})**\nPosition: #{state.queue.length}",
                title="Added to Queue",
            )

        if track.thumbnail_url:
            embed.set_thumbnail(url=track.thumbnail_url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="skip", aliases=["next"], description="Skip the current track.")
    @in_voice()
    @same_voice()
    async def skip(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id)
        if not state.is_playing:
            await ctx.send(embed=error_embed("Nothing to skip."))
            return

        skipped = state.current_track
        state.voice_client.stop()  # triggers after → _on_track_end → play_next

        # Wait briefly for the next track to start
        await asyncio.sleep(0.3)

        now_playing = state.current_track
        if now_playing and now_playing != skipped:
            embed = nowplaying_embed(now_playing, state)
            embed.description = f"Skipped **{skipped.display}**\n\nNow playing:"
            if now_playing.thumbnail_url:
                embed.set_thumbnail(url=now_playing.thumbnail_url)
            await ctx.send(embed=embed)
        else:
            msg = f"Skipped **{skipped.display}**" if skipped else "Skipped."
            await ctx.send(embed=success_embed(msg))

    @commands.hybrid_command(name="stop", description="Stop playback and clear the queue.")
    @in_voice()
    @same_voice()
    async def stop(self, ctx: commands.Context) -> None:
        await self.player.stop(ctx.guild.id)
        await ctx.send(embed=success_embed("Stopped and cleared queue."))

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show the currently playing track.")
    async def nowplaying(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id)
        track = state.current_track

        if not track or not state.is_playing:
            await ctx.send(embed=error_embed("Nothing is currently playing."))
            return

        embed = nowplaying_embed(track, state)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="volume", aliases=["vol"], description="Set the playback volume (0–200).")
    @in_voice()
    @same_voice()
    async def volume(self, ctx: commands.Context, volume: int) -> None:
        vol = max(0, min(200, volume)) / 100
        success = await self.player.set_volume(ctx.guild.id, vol)
        if success:
            await ctx.send(embed=success_embed(f"Volume set to **{volume}%**."))
        else:
            await ctx.send(embed=error_embed("Could not set volume."))


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(MusicCog(bot))
