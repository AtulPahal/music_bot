"""Core music playback commands supporting single tracks, playlists, search, and controls."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

from bot.audio.player import Player
from bot.audio.queue import Track
from bot.audio.source import extract_info, extract_playlist_entries, search_ytdl
from bot.ui.embeds import (
    error_embed,
    nowplaying_embed,
    playlist_added_embed,
    success_embed,
)
from bot.utils.checks import bot_has_voice_perms, in_voice, same_voice
from bot.utils.time import parse_duration
from bot.utils.url_helpers import extract_playlist_id, extract_video_id, is_playlist_url

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class MusicCog(commands.Cog, name="Music"):
    """Core music streaming commands."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot
        self.player = Player(bot)

    async def _resolve_query(
        self,
        query: str,
        requester_id: int,
        requester_name: str,
    ) -> tuple[Optional[Track], list[Track], Optional[str]]:
        """Resolve a query or URL to a single Track or a playlist of Tracks.

        Returns:
            (single_track, playlist_tracks, playlist_title)
        """
        clean_query = query.strip()

        # 1. Handle Playlist URLs
        if is_playlist_url(clean_query):
            playlist_id = extract_playlist_id(clean_query)
            log.info("Detected playlist query: %s (id: %s)", clean_query, playlist_id)

            tracks: list[Track] = []
            title = "YouTube Playlist"

            # Attempt extraction via YTMusic first if available
            if playlist_id and self.bot.ytmusic and self.bot.ytmusic.available:
                try:
                    data = await self.bot.ytmusic.get_playlist(playlist_id, limit=self.bot.config.voice.max_queue_length)
                    title = data.get("title", title)
                    entries = data.get("tracks", [])
                    for e in entries:
                        vid = e.get("videoId")
                        if not vid:
                            continue
                        artists_raw = e.get("artists", [])
                        artists = [a["name"] for a in artists_raw if isinstance(a, dict) and "name" in a]
                        dur_sec = e.get("duration_seconds", 0)
                        if not dur_sec:
                            dur_sec = parse_duration(e.get("duration", "0:00"))
                        thumbnails = e.get("thumbnails", [])
                        thumb = thumbnails[-1]["url"] if thumbnails else ""
                        tracks.append(
                            Track(
                                video_id=vid,
                                title=e.get("title", "Unknown"),
                                artists=artists,
                                duration=dur_sec,
                                thumbnail_url=thumb,
                                requester_id=requester_id,
                                requester_name=requester_name,
                                source_url=f"https://music.youtube.com/watch?v={vid}",
                            )
                        )
                except Exception as ex:
                    log.warning("YTMusic playlist lookup failed, falling back to yt-dlp: %s", ex)

            # Fallback to yt-dlp flat playlist extraction
            if not tracks:
                entries = await extract_playlist_entries(
                    clean_query,
                    limit=self.bot.config.voice.max_queue_length,
                    proxy=self.bot.config.audio.ytdl_proxy,
                    config=self.bot.config.audio,
                )
                for e in entries:
                    vid = e.get("id") or e.get("url")
                    if not vid:
                        continue
                    tracks.append(
                        Track(
                            video_id=vid,
                            title=e.get("title", "Unknown"),
                            artists=[e.get("uploader", "")] if e.get("uploader") else [],
                            duration=int(e.get("duration", 0) or 0),
                            thumbnail_url=e.get("thumbnail", ""),
                            requester_id=requester_id,
                            requester_name=requester_name,
                            source_url=f"https://youtu.be/{vid}",
                        )
                    )

            if tracks:
                return None, tracks, title

        # 2. Handle Direct Video URL or Bare ID
        video_id = extract_video_id(clean_query)
        if video_id:
            info = await extract_info(
                video_id,
                proxy=self.bot.config.audio.ytdl_proxy,
                config=self.bot.config.audio,
            )
            if info:
                title = info.get("title", "Unknown")
                duration = int(info.get("duration", 0) or 0)
                thumbnail = info.get("thumbnail", "")
                uploader = info.get("uploader", "")
                webpage_url = info.get("webpage_url", "")

                return (
                    Track(
                        video_id=video_id,
                        title=title,
                        artists=[uploader] if uploader else [],
                        duration=duration,
                        thumbnail_url=thumbnail,
                        requester_id=requester_id,
                        requester_name=requester_name,
                        source_url=webpage_url or clean_query,
                    ),
                    [],
                    None,
                )

        # 3. Handle Search Queries (YTMusic first, then yt-dlp fallback)
        if self.bot.ytmusic and self.bot.ytmusic.available:
            results = await self.bot.ytmusic.search(clean_query, filter="songs", limit=1)
            if results and results[0].get("videoId"):
                best = results[0]
                vid = best["videoId"]
                title = best.get("title", "Unknown")
                artists_raw = best.get("artists", [])
                artists = [a["name"] for a in artists_raw if isinstance(a, dict) and "name" in a]
                dur_sec = best.get("duration_seconds", 0)
                if not dur_sec:
                    dur_sec = parse_duration(best.get("duration", "0:00"))
                thumbnails = best.get("thumbnails", [])
                thumb = thumbnails[-1]["url"] if thumbnails else ""

                return (
                    Track(
                        video_id=vid,
                        title=title,
                        artists=artists,
                        duration=dur_sec,
                        thumbnail_url=thumb,
                        requester_id=requester_id,
                        requester_name=requester_name,
                    ),
                    [],
                    None,
                )

        # Fallback: yt-dlp search
        ytdl_results = await search_ytdl(
            clean_query,
            limit=1,
            proxy=self.bot.config.audio.ytdl_proxy,
            config=self.bot.config.audio,
        )
        if ytdl_results and (ytdl_results[0].get("id") or ytdl_results[0].get("url")):
            best_ytdl = ytdl_results[0]
            vid = best_ytdl.get("id") or best_ytdl.get("url", "")
            return (
                Track(
                    video_id=vid,
                    title=best_ytdl.get("title", "Unknown"),
                    artists=[best_ytdl.get("uploader", "")] if best_ytdl.get("uploader") else [],
                    duration=int(best_ytdl.get("duration", 0) or 0),
                    thumbnail_url=best_ytdl.get("thumbnail", ""),
                    requester_id=requester_id,
                    requester_name=requester_name,
                ),
                [],
                None,
            )

        return None, [], None

    # --- Commands ---

    @commands.hybrid_command(name="play", aliases=["p"], description="Play a song or playlist, or add it to the queue.")
    @in_voice()
    @bot_has_voice_perms()
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Search and play a song or playlist from YouTube Music / YouTube."""
        success, err = await self.player.join(ctx)
        if not success:
            await ctx.send(embed=error_embed(err, config=self.bot.config))
            return

        await ctx.defer()
        single, playlist_tracks, playlist_title = await self._resolve_query(
            query,
            ctx.author.id,
            ctx.author.display_name,
        )

        guild_id = ctx.guild.id
        state = self.player.get_state(guild_id)
        was_playing = state.is_playing or state.is_paused

        # Handle Playlist
        if playlist_tracks:
            added = await self.player.play_batch(guild_id, playlist_tracks)
            if added == 0:
                await ctx.send(embed=error_embed("Could not add playlist tracks (queue may be full).", config=self.bot.config))
                return

            total_dur = sum(t.duration for t in playlist_tracks[:added])
            first_thumb = playlist_tracks[0].thumbnail_url if playlist_tracks else ""
            embed = playlist_added_embed(
                title=playlist_title or "Playlist",
                count=added,
                total_duration=total_dur,
                url=query if is_playlist_url(query) else "",
                thumbnail_url=first_thumb,
                config=self.bot.config,
            )
            await ctx.send(embed=embed)
            return

        # Handle Single Track
        if single:
            state.queue.add(single)
            if not was_playing:
                await self.player._play_next(guild_id)
                embed = nowplaying_embed(single, state, config=self.bot.config)
            else:
                embed = success_embed(
                    f"Added to queue: **[{single.display}]({single.url})**\nPosition: `#{state.queue.length}`",
                    title="Added to Queue",
                    config=self.bot.config,
                )
                if single.thumbnail_url:
                    embed.set_thumbnail(url=single.thumbnail_url)
            await ctx.send(embed=embed)
            return

        await ctx.send(embed=error_embed(f"Could not find anything for: `{query}`", config=self.bot.config))

    @commands.hybrid_command(name="playskip", aliases=["ps"], description="Play a song immediately, skipping what is currently playing.")
    @in_voice()
    @same_voice()
    async def playskip(self, ctx: commands.Context, *, query: str) -> None:
        """Add a song to the front of the queue and skip directly to it."""
        await ctx.defer()
        single, _, _ = await self._resolve_query(query, ctx.author.id, ctx.author.display_name)
        if not single:
            await ctx.send(embed=error_embed(f"Could not find: `{query}`", config=self.bot.config))
            return

        guild_id = ctx.guild.id
        state = self.player.get_state(guild_id)
        state.queue.add(single, at_front=True)

        if state.is_playing:
            state.voice_client.stop()
        else:
            await self.player._play_next(guild_id)

        embed = success_embed(
            f"Playing now: **[{single.display}]({single.url})**",
            title="Skipped to Track",
            config=self.bot.config,
        )
        if single.thumbnail_url:
            embed.set_thumbnail(url=single.thumbnail_url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="playtop", aliases=["pt"], description="Add a song to the top of the queue to play next.")
    @in_voice()
    @same_voice()
    async def playtop(self, ctx: commands.Context, *, query: str) -> None:
        """Add a song to the front of the upcoming queue."""
        await ctx.defer()
        single, _, _ = await self._resolve_query(query, ctx.author.id, ctx.author.display_name)
        if not single:
            await ctx.send(embed=error_embed(f"Could not find: `{query}`", config=self.bot.config))
            return

        state = self.player.get_state(ctx.guild.id)
        state.queue.add(single, at_front=True)

        embed = success_embed(
            f"Added to top of queue: **[{single.display}]({single.url})**",
            title="Up Next",
            config=self.bot.config,
        )
        if single.thumbnail_url:
            embed.set_thumbnail(url=single.thumbnail_url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause", description="Pause current playback.")
    @in_voice()
    @same_voice()
    async def pause(self, ctx: commands.Context) -> None:
        success = await self.player.pause(ctx.guild.id)
        if success:
            await ctx.send(embed=success_embed("Playback paused.", config=self.bot.config))
        else:
            await ctx.send(embed=error_embed("Nothing is currently playing.", config=self.bot.config))

    @commands.hybrid_command(name="resume", aliases=["unpause"], description="Resume paused playback.")
    @in_voice()
    @same_voice()
    async def resume(self, ctx: commands.Context) -> None:
        success = await self.player.resume(ctx.guild.id)
        if success:
            await ctx.send(embed=success_embed("Playback resumed.", config=self.bot.config))
        else:
            await ctx.send(embed=error_embed("Playback is not paused.", config=self.bot.config))

    @commands.hybrid_command(name="skip", aliases=["s", "next"], description="Skip the current track.")
    @in_voice()
    @same_voice()
    async def skip(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id)
        if not state.is_playing and not state.is_paused:
            await ctx.send(embed=error_embed("Nothing is playing to skip.", config=self.bot.config))
            return

        skipped = state.current_track
        state.voice_client.stop()
        msg = f"Skipped **{skipped.display}**" if skipped else "Skipped track."
        await ctx.send(embed=success_embed(msg, title="Skipped", config=self.bot.config))

    @commands.hybrid_command(name="back", aliases=["prev"], description="Go back to the previously played track.")
    @in_voice()
    @same_voice()
    async def back(self, ctx: commands.Context) -> None:
        prev = await self.player.back(ctx.guild.id)
        if prev:
            await ctx.send(
                embed=success_embed(
                    f"Going back to **[{prev.display}]({prev.url})**",
                    title="Previous Track",
                    config=self.bot.config,
                )
            )
        else:
            await ctx.send(embed=error_embed("No previous track in history.", config=self.bot.config))

    @commands.hybrid_command(name="stop", description="Stop audio playback and clear the queue.")
    @in_voice()
    @same_voice()
    async def stop(self, ctx: commands.Context) -> None:
        await self.player.stop(ctx.guild.id)
        await ctx.send(embed=success_embed("Stopped playback and cleared queue.", title="Stopped", config=self.bot.config))

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Display the currently playing song and progress.")
    async def nowplaying(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id)
        if not state.current_track or not (state.is_playing or state.is_paused):
            await ctx.send(embed=error_embed("Nothing is currently playing.", config=self.bot.config))
            return

        embed = nowplaying_embed(
            state.current_track,
            state,
            config=self.bot.config,
            position_sec=state.elapsed_seconds,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="volume", aliases=["vol", "v"], description="Adjust playback volume (0 to 200%).")
    @in_voice()
    @same_voice()
    async def volume(self, ctx: commands.Context, volume: int) -> None:
        max_pct = int(self.bot.config.voice.max_volume * 100)
        min_pct = int(self.bot.config.voice.min_volume * 100)
        if not (min_pct <= volume <= max_pct):
            await ctx.send(
                embed=error_embed(
                    f"Volume must be between {min_pct}% and {max_pct}%.",
                    config=self.bot.config,
                )
            )
            return

        vol_float = volume / 100.0
        await self.player.set_volume(ctx.guild.id, vol_float)
        await ctx.send(embed=success_embed(f"Volume adjusted to **{volume}%**.", title="Volume", config=self.bot.config))

    @commands.hybrid_command(name="replay", aliases=["restart"], description="Replay the current track from the beginning.")
    @in_voice()
    @same_voice()
    async def replay(self, ctx: commands.Context) -> None:
        state = self.player.get_state(ctx.guild.id)
        if not state.current_track:
            await ctx.send(embed=error_embed("Nothing is currently playing.", config=self.bot.config))
            return

        current = state.current_track
        state.queue.add(current, at_front=True)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()
        else:
            await self.player._play_next(ctx.guild.id)

        await ctx.send(embed=success_embed(f"Replaying **{current.display}**", title="Replaying", config=self.bot.config))


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(MusicCog(bot))
