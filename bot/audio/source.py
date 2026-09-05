"""Audio stream and metadata extraction via yt-dlp with configuration support."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import yt_dlp

from bot.config import AudioConfig

log = logging.getLogger(__name__)


def build_ydl_options(config: Optional[AudioConfig] = None, proxy: str = "") -> dict[str, Any]:
    """Construct a dictionary of yt-dlp extraction options based on AudioConfig."""
    fmt = config.ytdl_format if config else "bestaudio/best"
    socket_timeout = config.ytdl_socket_timeout if config else 15
    default_search = config.ytdl_default_search if config else "ytsearch"

    opts: dict[str, Any] = {
        "format": fmt,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "default_search": default_search,
        "socket_timeout": socket_timeout,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "logtostderr": False,
    }

    effective_proxy = proxy or (config.ytdl_proxy if config else "")
    if effective_proxy:
        opts["proxy"] = effective_proxy

    if config and config.ytdl_cookies_file:
        opts["cookiefile"] = config.ytdl_cookies_file

    if config and config.ytdl_user_agent:
        opts["http_headers"] = {"User-Agent": config.ytdl_user_agent}

    return opts


async def get_stream_url(
    video_id: str,
    proxy: str = "",
    config: Optional[AudioConfig] = None,
    ydl_opts: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Extract direct audio-only stream URL for a YouTube video ID or URL."""
    url = video_id if video_id.startswith("http") else f"https://youtu.be/{video_id}"
    options = build_ydl_options(config, proxy)
    if ydl_opts:
        options.update(ydl_opts)

    loop = asyncio.get_running_loop()

    def _extract() -> Optional[str]:
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as exc:
                log.warning("yt-dlp extract failed for %s: %s", video_id, exc)
                return None

        if not info:
            return None

        # Direct format URL
        direct_url = info.get("url")
        if direct_url:
            return direct_url

        # Search inside formats
        formats = info.get("formats", [])
        audio_formats = [f for f in formats if f.get("acodec") and f["acodec"] != "none"]
        if not audio_formats:
            audio_formats = formats

        if audio_formats:
            best = max(audio_formats, key=lambda f: f.get("tbr", 0) or 0)
            stream_url = best.get("url") or best.get("manifest_url")
            if stream_url:
                return stream_url

        log.warning("No playable stream format found for %s", video_id)
        return None

    return await loop.run_in_executor(None, _extract)


async def extract_info(
    url_or_id: str,
    proxy: str = "",
    config: Optional[AudioConfig] = None,
    ydl_opts: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Extract full metadata dictionary for a video or URL without downloading."""
    url = url_or_id if url_or_id.startswith("http") else f"https://youtu.be/{url_or_id}"
    options = build_ydl_options(config, proxy)
    if ydl_opts:
        options.update(ydl_opts)

    loop = asyncio.get_running_loop()

    def _extract() -> Optional[dict[str, Any]]:
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except Exception as exc:
                log.warning("yt-dlp extract_info failed for %s: %s", url_or_id, exc)
                return None

    return await loop.run_in_executor(None, _extract)


async def extract_playlist_entries(
    playlist_url: str,
    limit: int = 100,
    proxy: str = "",
    config: Optional[AudioConfig] = None,
) -> list[dict[str, Any]]:
    """Extract flat entry list from a playlist URL."""
    options = build_ydl_options(config, proxy)
    options.update({
        "extract_flat": "in_playlist",
        "noplaylist": False,
        "playlistend": limit,
    })

    loop = asyncio.get_running_loop()

    def _extract() -> list[dict[str, Any]]:
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(playlist_url, download=False)
                if not info:
                    return []
                entries = info.get("entries", [])
                return [e for e in entries if e]
            except Exception as exc:
                log.warning("yt-dlp playlist extraction failed for %s: %s", playlist_url, exc)
                return []

    return await loop.run_in_executor(None, _extract)


async def search_ytdl(
    query: str,
    limit: int = 5,
    proxy: str = "",
    config: Optional[AudioConfig] = None,
) -> list[dict[str, Any]]:
    """Fallback search using yt-dlp ytsearch when YTMusic is unavailable."""
    options = build_ydl_options(config, proxy)
    options.update({
        "extract_flat": True,
        "noplaylist": True,
        "default_search": f"ytsearch{limit}",
    })

    loop = asyncio.get_running_loop()

    def _extract() -> list[dict[str, Any]]:
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                if not info:
                    return []
                entries = info.get("entries", [])
                return [e for e in entries if e]
            except Exception as exc:
                log.warning("yt-dlp search failed for '%s': %s", query, exc)
                return []

    return await loop.run_in_executor(None, _extract)
