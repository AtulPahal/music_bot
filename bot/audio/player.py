"""Per-guild audio player — manages playback state, auto-advance, disconnect timer."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord

from bot.audio.queue import Queue, RepeatMode, Track
from bot.audio.source import get_stream_url

log = logging.getLogger(__name__)


class Player:
    """Manages audio playback for a single guild via the bot instance.

    This is a stateless dispatcher; per-guild state lives in GuildVoiceState.
    """

    def __init__(self, bot) -> None:
        self.bot = bot

    @property
    def config(self):
        return self.bot.config

    # --- Voice channel management ---

    async def join(self, ctx) -> tuple[bool, str]:
        """Join the user's voice channel.

        Returns:
            (success: bool, error_message: str)
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            return False, "You are not connected to a voice channel."

        channel = ctx.author.voice.channel
        guild_id = ctx.guild.id
        state = self._get_state(guild_id)

        # Check the bot's permissions in the voice channel
        bot_member = ctx.guild.me
        perms = channel.permissions_for(bot_member)
        missing = []
        if not perms.connect:
            missing.append("Connect")
        if not perms.speak:
            missing.append("Speak")
        if missing:
            return False, (
                f"Missing permissions in {channel.mention}: **{' and '.join(missing)}**. "
                "Make sure the bot role has these permissions in the server and channel."
            )

        # Clean up stale voice client
        if state.voice_client and not state.voice_client.is_connected():
            try:
                await state.voice_client.disconnect(force=True)
            except Exception:
                pass
            state.voice_client = None

        # Connect or move
        if state.voice_client and state.voice_client.is_connected():
            if state.voice_client.channel.id == channel.id:
                state.text_channel_id = ctx.channel.id
                return True, ""
            try:
                await state.voice_client.move_to(channel)
            except discord.Forbidden:
                return False, f"Cannot move to {channel.mention} — missing permissions."
            except Exception as e:
                log.warning("move_to failed in guild %s: %s", guild_id, e)
                # Fall through to reconnect fresh
                try:
                    await state.voice_client.disconnect(force=True)
                except Exception:
                    pass
                state.voice_client = None

        if not state.voice_client:
            try:
                state.voice_client = await channel.connect(timeout=20.0)
            except discord.Forbidden:
                return False, (
                    f"Cannot connect to {channel.mention}. "
                    "The bot needs the **Connect** and **Speak** permissions "
                    "in both the server and this channel's permission overrides."
                )
            except asyncio.TimeoutError:
                return False, (
                    "Timed out trying to connect to the voice channel. "
                    "This can happen if Discord is having issues. Try again."
                )
            except Exception as e:
                err_str = str(e)
                log.warning("Failed to join VC in guild %s: %s", guild_id, err_str)
                if "74001" in err_str or "no such" in err_str.lower():
                    return False, (
                        "Voice connection failed. The bot might be missing the "
                        "**Voice Channel** permission at the server level, or FFmpeg "
                        "is not installed. Run `which ffmpeg` in your terminal."
                    )
                return False, f"Could not join voice channel: {err_str[:200]}"

        state.text_channel_id = ctx.channel.id
        return True, ""

    async def disconnect(self, guild_id: int) -> None:
        """Disconnect from voice and clean up state."""
        state = self._get_state(guild_id)
        self._cancel_disconnect_timer(state)

        if state.voice_client and state.voice_client.is_connected():
            await state.voice_client.disconnect(force=True)

        state.voice_client = None
        state.current_track = None
        state._suggest_task = None
        self.bot.guild_voice_states.pop(guild_id, None)

    # --- Playback control ---

    async def play(self, guild_id: int, track: Track) -> bool:
        """Add a track to the queue. If nothing is playing, start playback."""
        state = self._get_state(guild_id)
        self._cancel_disconnect_timer(state)

        state.queue.add(track)

        if not state.is_playing and not state.is_paused:
            return await self._play_next(guild_id)
        return True

    async def play_front(self, guild_id: int, track: Track) -> bool:
        """Add a track to the front of the queue. If nothing is playing, start."""
        state = self._get_state(guild_id)
        self._cancel_disconnect_timer(state)

        state.queue.add(track, at_front=True)

        if not state.is_playing and not state.is_paused:
            return await self._play_next(guild_id)
        return True

    async def back(self, guild_id: int) -> Optional[Track]:
        """Go back to the previous track in history."""
        state = self._get_state(guild_id)
        prev = state.queue.go_back()
        if prev is None:
            return None

        state._back_requested = True
        state.current_track = prev

        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()
        else:
            # Nothing playing, just play the previous track
            state._back_requested = False
            await self._play_next(guild_id)

        return prev

    async def skip(self, guild_id: int) -> Optional[Track]:
        """Skip the current track and play the next one."""
        state = self._get_state(guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()  # triggers after callback → play_next
        return state.current_track

    async def stop(self, guild_id: int) -> None:
        """Stop playback entirely, clear queue, keep voice connection."""
        state = self._get_state(guild_id)
        state.queue.clear()

        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()

        state.current_track = None
        self._start_disconnect_timer(state)

    async def pause(self, guild_id: int) -> bool:
        """Pause playback. Returns True if paused."""
        state = self._get_state(guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            return True
        return False

    async def resume(self, guild_id: int) -> bool:
        """Resume playback. Returns True if resumed."""
        state = self._get_state(guild_id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            return True
        return False

    async def set_volume(self, guild_id: int, volume: float) -> bool:
        """Set playback volume (0.0–2.0). Returns True if changed."""
        state = self._get_state(guild_id)
        state.volume = max(0.0, min(2.0, volume))
        if state.voice_client and state.voice_client.source:
            if isinstance(state.voice_client.source, discord.PCMVolumeTransformer):
                state.voice_client.source.volume = state.volume
                return True
        return False

    # --- Internal playback logic ---

    async def _play_next(self, guild_id: int) -> bool:
        """Play the next track in the queue. Returns False if queue is empty."""
        state = self._get_state(guild_id)

        if not state.voice_client or not state.voice_client.is_connected():
            log.warning("Not connected to voice in guild %s", guild_id)
            return False

        # Get next track
        track = state.queue.current
        if track is None:
            log.info("Queue empty in guild %s, stopping playback", guild_id)
            state.current_track = None
            await self._on_queue_end(guild_id)
            return False

        log.info("Playing track: %s (%s)", track.title, track.video_id)

        # Fetch stream URL if not already set
        if not track.stream_url:
            log.info("Extracting stream URL for %s...", track.video_id)
            url = await get_stream_url(track.video_id, proxy=self.config.YT_PROXY)
            if not url:
                log.warning("No stream URL found for %s (%s), skipping.", track.title, track.video_id)
                state.queue.skip()
                return await self._play_next(guild_id)
            track.stream_url = url
            log.info("Stream URL resolved for %s", track.video_id)

        state.current_track = track

        # Build FFmpeg audio source
        ffmpeg_opts = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -bufsize 64k",
        }

        try:
            source = discord.FFmpegPCMAudio(track.stream_url, **ffmpeg_opts)
            log.debug("FFmpegPCMAudio created for %s", track.video_id)
        except Exception as e:
            log.error("Failed to create FFmpeg source for %s: %s", track.video_id, e)
            state.queue.skip()
            return await self._play_next(guild_id)

        # Wrap in volume transformer (works because FFmpegPCMAudio outputs PCM)
        volume_source = discord.PCMVolumeTransformer(source, volume=state.volume)
        log.info("Starting playback in guild %s (volume=%.2f)", guild_id, state.volume)

        # Verify voice client is still connected
        if not state.voice_client or not state.voice_client.is_connected():
            log.warning("Voice client disconnected before play in guild %s", guild_id)
            return False

        def _after(error: Optional[Exception]) -> None:
            if error:
                log.warning("Playback error in guild %s: %s", guild_id, error)
            else:
                log.debug("Track finished normally in guild %s", guild_id)
            asyncio.run_coroutine_threadsafe(
                self._on_track_end(guild_id), self.bot.loop
            )

        try:
            state.voice_client.play(volume_source, after=_after)
        except Exception as e:
            log.exception(
                "voice_client.play() failed in guild %s: repr=%r",
                guild_id,
                e,
            )
            return False

        return True

    async def _on_track_end(self, guild_id: int) -> None:
        """Called when the current track finishes."""
        state = self._get_state(guild_id)

        # If this was a "back" command, don't advance position
        if state._back_requested:
            state._back_requested = False
            await self._play_next(guild_id)
            return

        next_track = state.queue.skip()

        if next_track is None:
            state.current_track = None
            await self._on_queue_end(guild_id)
        else:
            await self._play_next(guild_id)

    async def _on_queue_end(self, guild_id: int) -> None:
        """Called when the queue is empty and no loop is active."""
        state = self._get_state(guild_id)
        state.current_track = None

        # Auto-suggest via radio if enabled
        if self.config.YT_RADIO_ENABLED:
            last_track = state.queue.history[-1] if state.queue.history else None
            if last_track:
                await self._suggest_track(guild_id, last_track)
                return  # suggestion timer handles disconnect

        self._start_disconnect_timer(state)

    async def _suggest_track(self, guild_id: int, last_track: Track) -> None:
        """Fetch a radio suggestion and send it to the guild's text channel."""
        from bot.audio.autosuggest import SuggestionManager

        state = self._get_state(guild_id)
        if not self.bot.ytmusic or not self.bot.ytmusic.available:
            self._start_disconnect_timer(state)
            return

        manager = SuggestionManager(self.bot.ytmusic, self)
        state._suggest_task = asyncio.create_task(
            manager.fetch_and_suggest(guild_id, last_track)
        )

        # Start disconnect timer as fallback
        self._start_disconnect_timer(state)

    # --- Disconnect timer ---

    def _start_disconnect_timer(self, state) -> None:
        """Start a background task to disconnect after idle timeout."""
        self._cancel_disconnect_timer(state)

        async def _timer():
            await asyncio.sleep(self.config.AUTO_DISCONNECT_TIMEOUT)
            # Find guild_id for this state
            for gid, s in self.bot.guild_voice_states.items():
                if s is state:
                    if not state.is_playing and not state.is_paused:
                        log.info("Auto-disconnecting from guild %s (idle timeout)", gid)
                        await self.disconnect(gid)
                    break

        state._disconnect_task = asyncio.create_task(_timer())

    def _cancel_disconnect_timer(self, state) -> None:
        if state._disconnect_task and not state._disconnect_task.done():
            state._disconnect_task.cancel()
        state._disconnect_task = None

    # --- Helpers ---

    def _get_state(self, guild_id: int):
        """Get or create the GuildVoiceState for a guild."""
        if guild_id not in self.bot.guild_voice_states:
            from bot.bot import GuildVoiceState

            self.bot.guild_voice_states[guild_id] = GuildVoiceState()
        return self.bot.guild_voice_states[guild_id]

    def get_state(self, guild_id: int):
        """Public accessor for guild voice state."""
        return self._get_state(guild_id)
