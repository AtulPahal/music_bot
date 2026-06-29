"""Async wrapper around the synchronous ytmusicapi library.

All calls are dispatched to a ThreadPoolExecutor to avoid blocking
discord.py's async event loop.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from ytmusicapi import OAuthCredentials, YTMusic
from ytmusicapi.auth.types import AuthType

from bot.config import Config

log = logging.getLogger(__name__)


class YTMusicService:
    """Async-safe wrapper for ytmusicapi using a thread pool executor."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._yt: Optional[YTMusic] = None
        self._initialized = False

    @property
    def available(self) -> bool:
        return self._initialized and self._yt is not None

    def initialize(
        self,
        auth_file: str = "data/oauth.json",
        auth_mode: str = "none",
        client_id: str = "",
        client_secret: str = "",
    ) -> None:
        """Initialize the underlying YTMusic client.

        Gracefully degrades to unauthenticated mode when credentials are
        missing — search and playback still work.

        Args:
            auth_file: Path to OAuth JSON file or cookie headers file.
            auth_mode: 'oauth', 'cookie', or 'none'.
            client_id: Google OAuth client ID (optional for oauth mode).
            client_secret: Google OAuth client secret (optional for oauth mode).
        """
        auth_path = Path(auth_file)

        # Try OAuth with credentials
        if auth_mode == "oauth" and client_id and client_secret and auth_path.exists():
            try:
                credentials = OAuthCredentials(client_id=client_id, client_secret=client_secret)
                self._yt = YTMusic(str(auth_path), oauth_credentials=credentials)
                self._initialized = True
                log.info("YTMusic initialized with OAuth (file=%s)", auth_file)
                return
            except Exception as e:
                log.warning("OAuth init failed (%s), falling back to unauthenticated.", e)

        # Try browser cookie auth
        if auth_mode == "cookie" and auth_path.exists():
            try:
                self._yt = YTMusic(str(auth_path))
                self._initialized = True
                log.info("YTMusic initialized with browser cookie (file=%s)", auth_file)
                return
            except Exception as e:
                log.warning("Cookie auth failed (%s), falling back to unauthenticated.", e)

        # Fallback: unauthenticated mode (search + playback work)
        log.info(
            "YTMusic running in unauthenticated mode. "
            "Search and playback work; library/playlist features require "
            "OAuth setup (see README)."
        )
        self._yt = YTMusic()
        self._initialized = True

    async def _run(self, func) -> Any:
        """Run a callable in the executor thread.

        Args:
            func: A zero-argument callable (usually a lambda wrapping a ytmusicapi method).
        """
        if not self._yt:
            raise RuntimeError("YTMusic service not initialized")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func)

    async def search(self, query: str, filter: str = "songs", limit: int = 10) -> list[dict]:
        """Search YouTube Music.

        Args:
            query: Search string.
            filter: One of songs, videos, albums, artists, playlists.
            limit: Max results.

        Returns:
            List of search result dicts.
        """
        return await self._run(lambda: self._yt.search(query, filter=filter, limit=limit))

    async def get_song(self, video_id: str) -> dict:
        """Get metadata and streaming data for a video.

        NOTE: streaming URLs from this method are unreliable.
        Use yt-dlp for audio stream extraction instead.
        """
        return await self._run(lambda: self._yt.get_song(video_id))

    async def get_watch_playlist(
        self,
        video_id: Optional[str] = None,
        playlist_id: Optional[str] = None,
        limit: int = 25,
        radio: bool = False,
        shuffle: bool = False,
    ) -> dict:
        """Get a watch/radio playlist from YouTube Music.

        This is used for autoplay suggestions and radio mode.
        """
        return await self._run(lambda: self._yt.get_watch_playlist(
            videoId=video_id,
            playlistId=playlist_id,
            limit=limit,
            radio=radio,
            shuffle=shuffle,
        ))

    async def get_playlist(self, playlist_id: str, limit: int = 100) -> dict:
        """Get playlist contents."""
        return await self._run(lambda: self._yt.get_playlist(playlist_id, limit=limit))

    async def get_lyrics(self, browse_id: str) -> Optional[dict]:
        """Get lyrics for a song."""
        return await self._run(lambda: self._yt.get_lyrics(browse_id))

    async def rate_song(self, video_id: str, rating: str) -> dict:
        """Like/unlike a song. rating: 'LIKE', 'DISLIKE', 'INDIFFERENT'."""
        return await self._run(lambda: self._yt.rate_song(video_id, rating))

    async def get_history(self) -> list:
        """Get listen history."""
        return await self._run(lambda: self._yt.get_history())

    async def get_liked_songs(self, limit: int = 50) -> dict:
        """Get liked songs playlist."""
        return await self._run(lambda: self._yt.get_liked_songs(limit))

    async def close(self) -> None:
        """Clean up executor."""
        self._executor.shutdown(wait=False)
