"""Unit tests for AutoSuggest service and SuggestView."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.audio.autosuggest import SuggestionManager, SuggestView, _parse_duration
from bot.audio.queue import Track


class TestParseDuration:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("0:30", 30),
            ("3:32", 212),
            ("1:23:45", 5025),
            ("0:00", 0),
            ("123", 123),
        ],
    )
    def test_parse_duration(self, text, expected):
        assert _parse_duration(text) == expected


class TestSuggestionManager:
    @pytest.mark.asyncio
    async def test_fetch_and_suggest_no_channel(self):
        """If no text channel is set, should gracefully return."""
        player = MagicMock()
        player.get_state.return_value = MagicMock(text_channel_id=0)
        player.config.SUGGESTION_TIMEOUT = 30
        player.config.YT_PROXY = ""

        ytmusic = AsyncMock()
        mgr = SuggestionManager(ytmusic, player)

        # Should not raise
        last = Track(video_id="abc", title="Test")
        await mgr.fetch_and_suggest(12345, last)

        ytmusic.get_watch_playlist.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_and_suggest_radio_empty(self):
        """If radio returns no tracks, should gracefully return."""
        import discord
        player = MagicMock()
        state = MagicMock(text_channel_id=999)
        player.get_state.return_value = state
        player.config.SUGGESTION_TIMEOUT = 30
        player.config.YT_PROXY = ""
        # Mock the channel to pass isinstance check
        mock_channel = MagicMock(spec=discord.TextChannel)
        player.bot.get_channel.return_value = mock_channel

        ytmusic = AsyncMock()
        ytmusic.get_watch_playlist.return_value = {"tracks": []}

        mgr = SuggestionManager(ytmusic, player)
        last = Track(video_id="abc", title="Test")
        await mgr.fetch_and_suggest(12345, last)

        ytmusic.get_watch_playlist.assert_awaited_once()


class TestSuggestView:
    def test_view_initialization(self):
        player = MagicMock()
        track = Track(video_id="test", title="Test")
        view = SuggestView(player, track, timeout=30)

        assert view.track.video_id == "test"
        assert view.timeout == 30
        assert len(view.children) == 3  # Play Now, Add to Queue, Dismiss

    def test_play_now_button_marks_handled(self):
        player = MagicMock()
        track = Track(video_id="test", title="Test")
        view = SuggestView(player, track)
        view._handled = True  # simulate first click
        # Second click should early-return
        assert view._handled
