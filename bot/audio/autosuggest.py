"""Auto-suggest next track via YouTube Music radio when queue ends."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord

from bot.audio.queue import Track
from bot.audio.source import get_stream_url

log = logging.getLogger(__name__)


class SuggestView(discord.ui.View):
    """Buttons for the auto-suggest embed when queue ends."""

    def __init__(self, player, track: Track, timeout: int = 30) -> None:
        super().__init__(timeout=timeout)
        self.player = player
        self.track = track
        self._handled = False

    @discord.ui.button(emoji="\u25b6\ufe0f", label="Play Now", style=discord.ButtonStyle.success)
    async def play_now(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Add suggested track to front of queue and play immediately."""
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

        await interaction.response.edit_message(content="\u25b6\ufe0f Playing suggested track!", view=None)
        self.stop()

    @discord.ui.button(emoji="\u2795", label="Add to Queue", style=discord.ButtonStyle.secondary)
    async def add_to_queue(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Add suggested track to end of queue."""
        if self._handled:
            return
        self._handled = True

        guild_id = interaction.guild_id
        if guild_id is None:
            return

        state = self.player.get_state(guild_id)
        state.queue.add(self.track)

        await interaction.response.edit_message(content="\u2795 Added to queue!", view=None)
        self.stop()

    @discord.ui.button(emoji="\u274c", label="Dismiss", style=discord.ButtonStyle.danger)
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Dismiss the suggestion."""
        if self._handled:
            return
        self._handled = True
        await interaction.response.edit_message(content="Suggestion dismissed.", view=None)
        self.stop()

    async def on_timeout(self) -> None:
        """Auto-dismiss when the view times out."""
        self.clear_items()
        self.stop()


def _parse_duration(duration_str: str) -> int:
    """Parse a duration string like '3:32' or '1:03:22' to seconds."""
    parts = list(map(int, duration_str.split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] if parts else 0


class SuggestionManager:
    """Fetches radio suggestions via ytmusicapi when queue ends."""

    def __init__(self, ytmusic, player) -> None:
        self.ytmusic = ytmusic
        self.player = player

    async def fetch_and_suggest(self, guild_id: int, last_track: Track) -> None:
        """Fetch a radio suggestion based on the last track and send an embed.

        Called when the queue runs empty. Must be resilient to failures.
        """
        state = self.player.get_state(guild_id)

        # Determine which text channel to use
        channel_id = state.text_channel_id
        if not channel_id:
            return

        channel = self.player.bot.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        try:
            # Step 1: Fetch radio playlist from YouTube Music
            radio = await self.ytmusic.get_watch_playlist(
                video_id=last_track.video_id,
                radio=True,
                limit=1,
            )
            tracks = radio.get("tracks", [])
            if not tracks:
                log.info("No radio tracks returned for %s", last_track.video_id)
                return

            radio_track = tracks[0]
            video_id = radio_track.get("videoId")
            if not video_id:
                log.info("Radio track missing videoId for %s", last_track.video_id)
                return

            # Step 2: Get stream URL via yt-dlp
            stream_url = await get_stream_url(video_id, proxy=self.player.config.YT_PROXY)
            if not stream_url:
                log.info("Could not extract stream URL for suggested track %s", video_id)
                return

            # Step 3: Build Track object from radio data
            artists_raw = radio_track.get("artists", [])
            artists = [a["name"] for a in artists_raw if isinstance(a, dict) and "name" in a]

            thumbnails = radio_track.get("thumbnails", [])
            thumbnail_url = thumbnails[-1]["url"] if thumbnails else ""

            raw_duration = radio_track.get("duration_seconds", 0)
            if not raw_duration:
                raw_duration = _parse_duration(radio_track.get("duration", "0:00"))

            suggested = Track(
                video_id=video_id,
                title=radio_track.get("title", "Unknown"),
                artists=artists,
                duration=raw_duration,
                thumbnail_url=thumbnail_url,
                stream_url=stream_url,
            )

            state.suggested_track = suggested

            # Step 4: Build suggestion embed
            embed = discord.Embed(
                title="\U0001f3b5 Queue Ended \u2014 Suggested Next Track",
                description=f"[{suggested.display}]({suggested.url})",
                color=discord.Color.blue(),
            )
            if suggested.thumbnail_url:
                embed.set_thumbnail(url=suggested.thumbnail_url)
            embed.add_field(name="Duration", value=suggested.duration_str)
            embed.set_footer(text=f"Suggestion auto-dismisses in {self.player.config.SUGGESTION_TIMEOUT}s")

            # Step 5: Send with action buttons
            view = SuggestView(
                self.player,
                suggested,
                timeout=self.player.config.SUGGESTION_TIMEOUT,
            )
            await channel.send(embed=embed, view=view)

        except Exception as e:
            log.warning("Auto-suggest failed for guild %s: %s", guild_id, e)
