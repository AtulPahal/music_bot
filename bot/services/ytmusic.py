"""Asynchronous wrapper around the synchronous ytmusicapi library.

Only retains essential fetchers required by the music bot:
- search: Song and track searching
- get_watch_playlist: Radio autoplay suggestions
- get_playlist: YouTube / YouTube Music playlist importing
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from ytmusicapi import OAuthCredentials, YTMusic

log = logging.getLogger(__name__)


class YTMusicService:
    """Async-safe wrapper for ytmusicapi using a thread pool executor."""

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._yt: Optional[YTMusic] = None
        self._initialized: bool = False

    @property
    def available(self) -> bool:
        """Check if ytmusicapi client is initialized and ready."""
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
        missing -- search, radio, and playlist features still function normally.
        Args:
            auth_file: Path to OAuth JSON file or browser headers file.
            auth_mode: 'oauth', 'cookie', or 'none'.
            client_id: Google OAuth client ID (optional for oauth mode).
            client_secret: Google OAuth client secret (optional for oauth mode).
        """
        auth_path = Path(auth_file)

        # 1. Attempt OAuth with credentials if file exists
        if auth_mode == "oauth" and auth_path.exists():
            try:
                if client_id and client_secret:
                    credentials = OAuthCredentials(client_id=client_id, client_secret=client_secret)
                    self._yt = YTMusic(str(auth_path), oauth_credentials=credentials)
                else:
                    self._yt = YTMusic(str(auth_path))
                self._initialized = True
                log.info("YTMusic initialized with OAuth (file=%s)", auth_file)
                return
            except Exception as e:
                log.warning("OAuth init failed (%s), falling back to unauthenticated.", e)

        # 2. Attempt browser cookie auth if file exists
        if auth_mode == "cookie" and auth_path.exists():
            try:
                self._yt = YTMusic(str(auth_path))
                self._initialized = True
                log.info("YTMusic initialized with browser headers (file=%s)", auth_file)
                return
            except Exception as e:
                log.warning("Cookie auth failed (%s), falling back to unauthenticated.", e)

        # 3. Fallback: unauthenticated mode
        try:
            self._yt = YTMusic()
            self._initialized = True
            log.info("YTMusic running in unauthenticated mode.")
        except Exception as e:
            log.error("Failed to initialize YTMusic client: %s", e)
            self._yt = None
            self._initialized = False

    async def _run(self, func) -> Any:
        """Execute a callable inside the worker thread pool."""
        if not self._yt:
            raise RuntimeError("YTMusic service is not initialized")
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(self._executor, func)
        except Exception as e:
            log.warning("YTMusic execution error: %s", e)
            return None

    async def search(self, query: str, filter: str = "songs", limit: int = 10) -> list[dict[str, Any]]:
        """Search YouTube Music for tracks."""
        res = await self._run(lambda: self._yt.search(query, filter=filter, limit=limit))
        return res if isinstance(res, list) else []

    async def get_watch_playlist(
        self,
        video_id: Optional[str] = None,
        playlist_id: Optional[str] = None,
        limit: int = 25,
        radio: bool = False,
        shuffle: bool = False,
    ) -> dict[str, Any]:
        """Fetch watch/radio playlist from YouTube Music for autoplay suggestions."""
        res = await self._run(lambda: self._yt.get_watch_playlist(
            videoId=video_id,
            playlistId=playlist_id,
            limit=limit,
            radio=radio,
            shuffle=shuffle,
        ))
        return res if isinstance(res, dict) else {"tracks": []}

    async def get_playlist(self, playlist_id: str, limit: int = 100) -> dict[str, Any]:
        """Fetch playlist contents from YouTube Music."""
        res = await self._run(lambda: self._yt.get_playlist(playlist_id, limit=limit))
        return res if isinstance(res, dict) else {"tracks": []}

    async def close(self) -> None:
        """Shutdown executor threads cleanly."""
        self._executor.shutdown(wait=False)
