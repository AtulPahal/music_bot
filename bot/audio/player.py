"""Per-guild audio player managing state, voice connections, stream playback, and lifecycle."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional

import discord

from bot.audio.queue import Queue, RepeatMode, Track
from bot.audio.source import get_stream_url
from bot.config import Config

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class GuildVoiceState:
    """Per-guild audio playback and voice connection state."""

    def __init__(self, max_queue_length: int = 500, default_volume: float = 0.5) -> None:
        self.voice_client: Optional[discord.VoiceClient] = None
        self.text_channel_id: int = 0
        self.current_track: Optional[Track] = None
        self.queue: Queue = Queue(max_length=max_queue_length)
        self.repeat_mode: RepeatMode = RepeatMode.OFF
        self.shuffle: bool = False
        self.volume: float = default_volume
        self.playback_start_time: float = 0.0
        self.paused_duration: float = 0.0
        self._pause_start_time: float = 0.0

        self.lock: asyncio.Lock = asyncio.Lock()
        self._disconnect_task: Optional[asyncio.Task] = None
        self._suggest_task: Optional[asyncio.Task] = None
        self.suggested_track: Optional[Track] = None
        self._back_requested: bool = False

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self.voice_client is not None and self.voice_client.is_playing()

    @property
    def is_paused(self) -> bool:
        """Check if audio is currently paused."""
        return self.voice_client is not None and self.voice_client.is_paused()

    @property
    def is_connected(self) -> bool:
        """Check if voice client is connected."""
        return self.voice_client is not None and self.voice_client.is_connected()

    @property
    def elapsed_seconds(self) -> int:
        """Calculate elapsed playback seconds for the currently playing track."""
        if not self.is_playing and not self.is_paused:
            return 0
        if self.playback_start_time <= 0:
            return 0

        now = time.time()
        if self.is_paused and self._pause_start_time > 0:
            active_pause = now - self._pause_start_time
        else:
            active_pause = 0.0

        elapsed = now - self.playback_start_time - self.paused_duration - active_pause
        return max(0, int(elapsed))


class Player:
    """Manages playback, voice channels, and track advancement for guilds."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    @property
    def config(self) -> Config:
        return self.bot.config

    def _get_state(self, guild_id: int) -> GuildVoiceState:
        """Retrieve or create the GuildVoiceState for a guild."""
        if guild_id not in self.bot.guild_voice_states:
            self.bot.guild_voice_states[guild_id] = GuildVoiceState(
                max_queue_length=self.config.voice.max_queue_length,
                default_volume=self.config.voice.default_volume,
            )
        return self.bot.guild_voice_states[guild_id]

    def get_state(self, guild_id: int) -> GuildVoiceState:
        """Public accessor for guild voice state."""
        return self._get_state(guild_id)

    # --- Voice Connection Management ---

    async def join(self, ctx) -> tuple[bool, str]:
        """Join or move to the command author's voice channel.

        Returns:
            (success: bool, message: str)
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            return False, "You are not connected to a voice channel."

        channel = ctx.author.voice.channel
        guild = ctx.guild
        guild_id = guild.id
        state = self._get_state(guild_id)

        # Check permissions
        bot_member = guild.me
        perms = channel.permissions_for(bot_member)
        missing: list[str] = []
        if not perms.connect:
            missing.append("Connect")
        if not perms.speak:
            missing.append("Speak")
        if missing:
            return False, (
                f"Missing permissions in {channel.mention}: **{' and '.join(missing)}**. "
                "Please grant these permissions to the bot role."
            )

        # Clean up stale / dead voice client
        if state.voice_client and not state.voice_client.is_connected():
            try:
                await state.voice_client.disconnect(force=True)
            except Exception:
                pass
            state.voice_client = None

        # Move or connect
        if state.voice_client and state.voice_client.is_connected():
            if state.voice_client.channel.id == channel.id:
                state.text_channel_id = ctx.channel.id
                return True, ""
            try:
                await state.voice_client.move_to(channel)
                state.text_channel_id = ctx.channel.id
                return True, ""
            except Exception as e:
                log.warning("Failed to move voice channel in guild %s: %s", guild_id, e)
                try:
                    await state.voice_client.disconnect(force=True)
                except Exception:
                    pass
                state.voice_client = None

        # Fresh connection
        if not state.voice_client:
            try:
                timeout = self.config.voice.connect_timeout
                state.voice_client = await channel.connect(timeout=timeout)
            except discord.Forbidden:
                return False, f"Permission denied when connecting to {channel.mention}."
            except asyncio.TimeoutError:
                return False, "Connection to voice channel timed out. Please try again."
            except Exception as e:
                log.error("Voice connect error in guild %s: %s", guild_id, e)
                return False, f"Could not connect to voice: {e}"

        state.text_channel_id = ctx.channel.id
        return True, ""

    async def disconnect(self, guild_id: int) -> None:
        """Disconnect from voice and clean up all state and tasks."""
        state = self._get_state(guild_id)
        self._cancel_disconnect_timer(state)

        if state._suggest_task and not state._suggest_task.done():
            state._suggest_task.cancel()
        state._suggest_task = None

        if state.voice_client and state.voice_client.is_connected():
            try:
                await state.voice_client.disconnect(force=True)
            except Exception:
                pass

        state.voice_client = None
        state.current_track = None
        self.bot.guild_voice_states.pop(guild_id, None)

    # --- Playback Operations ---

    async def play(self, guild_id: int, track: Track) -> bool:
        """Queue a track and initiate playback if currently idle."""
        state = self._get_state(guild_id)
        self._cancel_disconnect_timer(state)

        if not state.queue.add(track):
            return False

        if not state.is_playing and not state.is_paused:
            return await self._play_next(guild_id)
        return True

    async def play_front(self, guild_id: int, track: Track) -> bool:
        """Queue a track at the front of the queue."""
        state = self._get_state(guild_id)
        self._cancel_disconnect_timer(state)

        if not state.queue.add(track, at_front=True):
            return False

        if not state.is_playing and not state.is_paused:
            return await self._play_next(guild_id)
        return True

    async def play_batch(self, guild_id: int, tracks: list[Track]) -> int:
        """Add multiple tracks to the queue (e.g. from playlist) and start if idle."""
        state = self._get_state(guild_id)
        self._cancel_disconnect_timer(state)

        added = state.queue.extend(tracks)
        if added > 0 and not state.is_playing and not state.is_paused:
            await self._play_next(guild_id)
        return added

    async def skip(self, guild_id: int) -> Optional[Track]:
        """Skip currently playing track."""
        state = self._get_state(guild_id)
        skipped = state.current_track
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()
        return skipped

    async def back(self, guild_id: int) -> Optional[Track]:
        """Play previous track from playback history."""
        state = self._get_state(guild_id)
        prev = state.queue.go_back()
        if not prev:
            return None

        state._back_requested = True
        state.current_track = prev

        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()
        else:
            state._back_requested = False
            await self._play_next(guild_id)

        return prev

    async def pause(self, guild_id: int) -> bool:
        """Pause playback."""
        state = self._get_state(guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            state._pause_start_time = time.time()
            return True
        return False

    async def resume(self, guild_id: int) -> bool:
        """Resume playback."""
        state = self._get_state(guild_id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            if state._pause_start_time > 0:
                state.paused_duration += time.time() - state._pause_start_time
                state._pause_start_time = 0.0
            return True
        return False

    async def stop(self, guild_id: int) -> None:
        """Stop playback, clear queue, and begin idle disconnect timer."""
        state = self._get_state(guild_id)
        state.queue.clear()

        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.voice_client.stop()

        state.current_track = None
        self._start_disconnect_timer(state, guild_id)

    async def set_volume(self, guild_id: int, volume: float) -> bool:
        """Set volume (bounded between configured min and max volume)."""
        state = self._get_state(guild_id)
        min_v = self.config.voice.min_volume
        max_v = self.config.voice.max_volume
        bounded_volume = max(min_v, min(max_v, volume))
        state.volume = bounded_volume

        if state.voice_client and state.voice_client.source:
            if isinstance(state.voice_client.source, discord.PCMVolumeTransformer):
                state.voice_client.source.volume = state.volume
                return True
        return True

    # --- Internal Playback Engine ---

    async def _play_next(self, guild_id: int) -> bool:
        """Internal worker to stream the next available track."""
        state = self._get_state(guild_id)

        async with state.lock:
            if not state.voice_client or not state.voice_client.is_connected():
                log.warning("VoiceClient disconnected before play in guild %s", guild_id)
                return False

            track = state.queue.current
            if track is None:
                state.current_track = None
                await self._on_queue_end(guild_id)
                return False

            # Extract stream URL if not cached
            if not track.stream_url:
                log.info("Extracting stream URL for track %s (%s)", track.title, track.video_id)
                url = await get_stream_url(
                    track.video_id,
                    proxy=self.config.audio.ytdl_proxy,
                    config=self.config.audio,
                )
                if not url:
                    log.warning("Failed to extract stream for %s, skipping to next.", track.video_id)
                    state.queue.skip()
                    return await self._play_next(guild_id)
                track.stream_url = url
                log.info("Stream URL resolved successfully for %s", track.video_id)
            state.current_track = track

            # Build FFmpeg audio source with configured options
            ffmpeg_before = self.config.audio.ffmpeg_before_options
            ffmpeg_opts = self.config.audio.ffmpeg_options
            ffmpeg_bin = self.config.audio.ffmpeg_bin

            try:
                source = discord.FFmpegPCMAudio(
                    track.stream_url,
                    executable=ffmpeg_bin,
                    before_options=ffmpeg_before,
                    options=ffmpeg_opts,
                )
            except Exception as e:
                log.error("FFmpeg initialization error for %s: %s", track.video_id, e)
                state.queue.skip()
                return await self._play_next(guild_id)

            volume_source = discord.PCMVolumeTransformer(source, volume=state.volume)
            state.playback_start_time = time.time()
            state.paused_duration = 0.0
            state._pause_start_time = 0.0

            def _after_callback(error: Optional[Exception]) -> None:
                if error:
                    log.warning("Playback finished with error in guild %s: %s", guild_id, error)
                asyncio.run_coroutine_threadsafe(
                    self._on_track_end(guild_id), self.bot.loop
                )

            try:
                state.voice_client.play(volume_source, after=_after_callback)
                log.info("Playback started: '%s' in guild %s (vol=%.2f)", track.title, guild_id, state.volume)
                return True
            except Exception as e:
                log.exception("voice_client.play exception in guild %s: %s", guild_id, e)
                return False

    async def _on_track_end(self, guild_id: int) -> None:
        """Callback invoked when the current track finishes streaming."""
        state = self._get_state(guild_id)

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
        """Invoked when queue is empty."""
        state = self._get_state(guild_id)
        state.current_track = None

        if self.config.ytmusic.radio_enabled:
            last_track = state.queue.history[-1] if state.queue.history else None
            if last_track:
                await self._suggest_track(guild_id, last_track)
                return

        self._start_disconnect_timer(state, guild_id)

    async def _suggest_track(self, guild_id: int, last_track: Track) -> None:
        """Trigger auto-suggest radio recommendation for the guild."""
        from bot.audio.autosuggest import SuggestionManager

        state = self._get_state(guild_id)
        manager = SuggestionManager(self.bot.ytmusic, self)
        state._suggest_task = asyncio.create_task(
            manager.fetch_and_suggest(guild_id, last_track)
        )
        self._start_disconnect_timer(state, guild_id)

    # --- Inactivity Disconnect Timer ---

    def _start_disconnect_timer(self, state: GuildVoiceState, guild_id: int) -> None:
        """Start auto-disconnect countdown when idle."""
        self._cancel_disconnect_timer(state)
        timeout = self.config.voice.auto_disconnect_timeout

        async def _timer() -> None:
            await asyncio.sleep(timeout)
            if not state.is_playing and not state.is_paused:
                log.info("Auto-disconnecting from guild %s due to inactivity (%ss timeout)", guild_id, timeout)
                await self.disconnect(guild_id)

        state._disconnect_task = asyncio.create_task(_timer())

    def _cancel_disconnect_timer(self, state: GuildVoiceState) -> None:
        """Cancel running disconnect countdown."""
        if state._disconnect_task and not state._disconnect_task.done():
            state._disconnect_task.cancel()
        state._disconnect_task = None
