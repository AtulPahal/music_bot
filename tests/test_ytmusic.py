"""Unit tests for YTMusicService and URL helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bot.services.ytmusic import YTMusicService
from bot.utils.url_helpers import extract_video_id, is_youtube_url


class TestYTMusicService:
    def test_initial_not_available(self):
        svc = YTMusicService()
        assert not svc.available

    def test_initialize_unauthenticated(self):
        """If auth file doesn't exist, init should still work (unauthenticated)."""
        svc = YTMusicService()
        svc.initialize(auth_file="nonexistent.json")
        assert svc.available

    def test_search_requires_init(self):
        svc = YTMusicService()
        with pytest.raises(RuntimeError):
            import asyncio
            asyncio.run(svc.search("test"))


class TestURLHelpers:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://music.youtube.com/watch?v=dQw4w9WgXcQ&list=PL...", "dQw4w9WgXcQ"),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?si=abc123", "dQw4w9WgXcQ"),
            ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),  # bare video ID
            ("just a song name", None),
            ("", None),
            ("https://open.spotify.com/track/abc", None),
        ],
    )
    def test_extract_video_id(self, url, expected):
        assert extract_video_id(url) == expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("https://youtu.be/dQw4w9WgXcQ", True),
            ("hello world", False),
        ],
    )
    def test_is_youtube_url(self, text, expected):
        assert is_youtube_url(text) == expected
