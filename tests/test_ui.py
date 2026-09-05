"""Unit tests for UI utilities, progress bars, and embed generation."""

from __future__ import annotations

import discord
import pytest

from bot.audio.queue import Queue, RepeatMode, Track
from bot.config import Config, DiscordConfig, UIThemeConfig
from bot.ui.embeds import (
    error_embed,
    nowplaying_embed,
    playlist_added_embed,
    queue_embed,
    search_embed,
    success_embed,
)
from bot.utils.time import create_progress_bar, format_duration, parse_duration


class TestTimeUtils:
    def test_format_duration(self):
        assert format_duration(30) == "0:30"
        assert format_duration(212) == "3:32"
        assert format_duration(3665) == "1:01:05"
        assert format_duration(-10) == "0:00"

    def test_parse_duration(self):
        assert parse_duration("0:30") == 30
        assert parse_duration("3:32") == 212
        assert parse_duration("1:01:05") == 3665
        assert parse_duration("invalid") == 0

    def test_create_progress_bar(self):
        bar = create_progress_bar(50, 100, length=12)
        assert "o" in bar
        assert bar.startswith("[")
        assert bar.endswith("]")
        assert len(bar) == 12

        bar_start = create_progress_bar(0, 100, length=12)
        assert bar_start.startswith("[o")

        bar_end = create_progress_bar(100, 100, length=12)
        assert bar_end.endswith("o]")


class TestEmbedBuilders:
    @pytest.fixture
    def mock_config(self) -> Config:
        return Config(
            discord=DiscordConfig(bot_token="test_token", client_id="123456"),
            ui=UIThemeConfig(),
        )

    def test_nowplaying_embed(self, mock_config):
        track = Track(
            video_id="test1234567",
            title="Cool Track",
            artists=["Famous Artist"],
            duration=200,
            thumbnail_url="https://example.com/thumb.jpg",
            requester_name="TestUser",
        )
        embed = nowplaying_embed(track, config=mock_config, position_sec=50)
        assert isinstance(embed, discord.Embed)
        assert "Cool Track" in embed.description
        assert embed.thumbnail.url == "https://example.com/thumb.jpg"
        assert embed.title == "Now Playing"

    def test_queue_embed(self, mock_config):
        q = Queue()
        q.add(Track(video_id="1", title="Song 1", duration=100))
        q.add(Track(video_id="2", title="Song 2", duration=200))
        embed = queue_embed(q, config=mock_config)
        assert isinstance(embed, discord.Embed)
        assert "Song 1" in embed.description
        assert embed.title == "Music Queue"

    def test_playlist_added_embed(self, mock_config):
        embed = playlist_added_embed(
            title="My Playlist",
            count=25,
            total_duration=5000,
            url="https://youtube.com/playlist?list=123",
            config=mock_config,
        )
        assert isinstance(embed, discord.Embed)
        assert "My Playlist" in embed.description
        assert embed.title == "Playlist Added to Queue"

    def test_status_embeds(self, mock_config):
        err = error_embed("Something went wrong", config=mock_config)
        assert err.color == mock_config.ui.color_error
        assert err.title == "Error"

        succ = success_embed("Operation succeeded", config=mock_config)
        assert succ.color == mock_config.ui.color_success
        assert succ.title == "Success"
