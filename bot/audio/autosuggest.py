"""Auto-suggest next track via YouTube Music radio and fallback mechanisms when queue ends."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

import discord

from bot.audio.queue import Track
from bot.audio.source import get_stream_url, search_ytdl
from bot.config import Config
from bot.utils.time import format_duration, parse_duration

if TYPE_CHECKING:
    from bot.audio.player import Player

log = logging.getLogger(__name__)


class SuggestView(discord.ui.View):
    """Interactive view for radio track recommendations when queue runs dry."""

    def __init__(self, player: "Player", track: Track, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)
        self.player = player
        self.track = track
        self._handled = False

    @discord.ui.button(label="Play Now", style=discord.ButtonStyle.success, custom_id="sugg_play_now")
    async def play_now_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._handled:
            return
        self._handled = True

        guild_id = interaction.guild_id
        if guild_id is None:
            return

        state = self.player.get_state(guild_id)
        state.queue.add(self.track, at_front=True)

        if not state.is_playing and not state.is_paused:
            await self.player._play_next(guild_id)

        await interaction.response.edit_message(
            content=f"Playing suggested track: {self.track.display}",
            view=None,
        )
        self.stop()

    @discord.ui.button(label="Add to Queue", style=discord.ButtonStyle.secondary, custom_id="sugg_add_queue")
    async def add_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._handled:
            return
        self._handled = True

        guild_id = interaction.guild_id
        if guild_id is None:
            return

        state = self.player.get_state(guild_id)
        state.queue.add(self.track)

        await interaction.response.edit_message(
            content=f"Added to queue: {self.track.display}",
            view=None,
        )
        self.stop()

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.danger, custom_id="sugg_dismiss")
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._handled:
            return
        self._handled = True
        await interaction.response.edit_message(content="Suggestion dismissed.", view=None)
        self.stop()

    async def on_timeout(self) -> None:
        self.clear_items()
        self.stop()


def _parse_duration(duration_str: str) -> int:
    """Parse a duration string to seconds."""
    return parse_duration(duration_str)


_parse_duration_string = _parse_duration


class SuggestionManager:
    """Manages radio recommendations via YouTube Music with fallback to search."""

    def __init__(self, ytmusic, player: "Player") -> None:
        self.ytmusic = ytmusic
        self.player = player

    async def fetch_and_suggest(self, guild_id: int, last_track: Track) -> None:
        """Fetch a recommendation and send an interactive embed to the guild's text channel."""
        state = self.player.get_state(guild_id)
        channel_id = state.text_channel_id
        if not channel_id:
            return

        channel = self.player.bot.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.abc.Messageable):
            return

        try:
            suggested: Optional[Track] = None

            # 1. Try YTMusic watch playlist (radio)
            if self.ytmusic and self.ytmusic.available:
                radio_data = await self.ytmusic.get_watch_playlist(
                    video_id=last_track.video_id,
                    radio=True,
                    limit=5,
                )
                tracks = radio_data.get("tracks", [])
                for candidate in tracks:
                    vid = candidate.get("videoId")
                    if vid and vid != last_track.video_id:
                        artists_raw = candidate.get("artists", [])
                        artists = [a["name"] for a in artists_raw if isinstance(a, dict) and "name" in a]
                        thumbnails = candidate.get("thumbnails", [])
                        thumbnail_url = thumbnails[-1]["url"] if thumbnails else ""
                        dur_sec = candidate.get("duration_seconds", 0)
                        if not dur_sec:
                            dur_sec = parse_duration(candidate.get("duration", "0:00"))

                        suggested = Track(
                            video_id=vid,
                            title=candidate.get("title", "Unknown"),
                            artists=artists,
                            duration=dur_sec,
                            thumbnail_url=thumbnail_url,
                            is_suggested=True,
                        )
                        break

            # 2. Fallback to yt-dlp search if YTMusic gave no results
            if not suggested:
                ytdl_results = await search_ytdl(
                    query=f"{last_track.title} {last_track.artist_str}",
                    limit=3,
                    config=self.player.config.audio,
                )
                for res in ytdl_results:
                    res_id = res.get("id") or res.get("url")
                    if res_id and res_id != last_track.video_id:
                        suggested = Track(
                            video_id=res_id,
                            title=res.get("title", "Unknown"),
                            artists=[res.get("uploader", "")] if res.get("uploader") else [],
                            duration=int(res.get("duration", 0) or 0),
                            thumbnail_url=res.get("thumbnail", ""),
                            is_suggested=True,
                        )
                        break

            if not suggested:
                log.info("No radio suggestions found for %s in guild %s", last_track.video_id, guild_id)
                return

            state.suggested_track = suggested
            cfg = self.player.config

            # Build suggestion embed
            embed = discord.Embed(
                title="Autoplay Recommendation",
                description=f"Queue ended. Next recommendation:\n**[{suggested.display}]({suggested.url})**",
                color=cfg.ui.color_primary,
            )
            if suggested.thumbnail_url:
                embed.set_thumbnail(url=suggested.thumbnail_url)
            embed.add_field(name="Duration", value=f"`{suggested.duration_str}`", inline=True)
            embed.set_footer(text=f"Auto-dismisses in {cfg.ytmusic.suggestion_timeout} seconds")

            view = SuggestView(
                self.player,
                suggested,
                timeout=cfg.ytmusic.suggestion_timeout,
            )
            await channel.send(embed=embed, view=view)

        except Exception as e:
            log.warning("Auto-suggest error in guild %s: %s", guild_id, e)
