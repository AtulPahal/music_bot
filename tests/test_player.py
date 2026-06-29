"""Unit tests for Player and GuildVoiceState."""

from __future__ import annotations

import pytest

from bot.audio.queue import Queue, Track
from bot.bot import GuildVoiceState


class TestGuildVoiceState:
    def test_initial_state(self):
        state = GuildVoiceState()
        assert state.voice_client is None
        assert state.current_track is None
        assert not state.is_playing
        assert not state.is_paused
        assert not state.is_connected

    def test_repeat_mode_default(self):
        from bot.audio.queue import RepeatMode

        state = GuildVoiceState()
        assert state.repeat_mode == RepeatMode.OFF


class TestQueueEdgeCases:
    def test_empty_queue_properties(self):
        q = Queue()
        assert q.is_empty
        assert not q.is_full
        assert q.current is None
        assert q.upcoming == []
        assert q.history == []
        assert q.length == 0
        assert q.position == 0

    def test_single_track_queue(self):
        q = Queue()
        track = Track(video_id="single", title="Only One")
        q.add(track)

        assert q.length == 1
        assert q.current is not None
        assert q.current.video_id == "single"

        # Skip should make queue empty (skip returns new current = None)
        result = q.skip()
        assert result is None
        assert q.current is None

    def test_remove_duplicates_on_empty(self):
        q = Queue()
        assert q.remove_duplicates() == 0

    def test_shuffle_empty(self):
        q = Queue()
        q.shuffle()  # should not crash
        assert q.is_empty

    def test_clear_empty(self):
        q = Queue()
        q.clear()  # should not crash
        assert q.is_empty


class TestTrackEdgeCases:
    def test_track_empty_artists(self):
        t = Track(video_id="v1", title="Song")
        assert t.display == "Song"
        assert t.duration_str == "0:00"

    def test_track_with_all_fields(self):
        t = Track(
            video_id="v1",
            title="Test Song",
            artists=["Test Artist"],
            duration=300,
            thumbnail_url="https://example.com/thumb.jpg",
            stream_url="https://example.com/audio",
            requester_id=12345,
            source_url="https://youtu.be/v1",
        )
        assert t.display == "Test Artist - Test Song"
        assert "music.youtube.com" in t.url
        assert t.duration_str == "5:00"

    def test_track_defaults(self):
        t = Track(video_id="test123", title="test123")
        assert t.title == "test123"
        assert t.artists == []
        assert t.duration == 0
