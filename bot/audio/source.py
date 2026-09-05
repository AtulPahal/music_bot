"""Audio stream and metadata extraction via yt-dlp with configuration support and datacenter bypass."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Any, Optional

import yt_dlp

from bot.config import AudioConfig

log = logging.getLogger(__name__)

# Track temporary cookie file if created from environment text
_TEMP_COOKIE_FILE: Optional[str] = None


def _get_cookie_file(config: Optional[AudioConfig]) -> Optional[str]:
    """Resolve cookie file from direct path or text environment variable."""
    global _TEMP_COOKIE_FILE
    if not config:
        return None

    if config.ytdl_cookies_file and os.path.exists(config.ytdl_cookies_file):
        return config.ytdl_cookies_file

    if config.ytdl_cookies_text:
        if _TEMP_COOKIE_FILE and os.path.exists(_TEMP_COOKIE_FILE):
            return _TEMP_COOKIE_FILE
        try:
            fd, path = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(config.ytdl_cookies_text)
            _TEMP_COOKIE_FILE = path
            return path
        except Exception as e:
            log.warning("Could not write cookie file from environment text: %s", e)

    return None


def build_ydl_options(config: Optional[AudioConfig] = None, proxy: str = "") -> dict[str, Any]:
    """Construct a dictionary of yt-dlp extraction options based on AudioConfig."""
    fmt = config.ytdl_format if config else "bestaudio/best"
    socket_timeout = config.ytdl_socket_timeout if config else 15
    default_search = config.ytdl_default_search if config else "ytsearch"
    player_clients = config.ytdl_player_clients if config else ["android"]
    player_skip = config.ytdl_player_skip if config else ["configs", "webpage"]

    extractor_args: dict[str, Any] = {
        "youtube": {
            "player_client": player_clients,
            "player_skip": player_skip,
        }
    }
    if config and config.ytdl_po_token:
        extractor_args["youtube"]["po_token"] = [config.ytdl_po_token]

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
        "extractor_args": extractor_args,
    }

    effective_proxy = proxy or (config.ytdl_proxy if config else "")
    if effective_proxy:
        opts["proxy"] = effective_proxy

    cookie_file = _get_cookie_file(config)
    if cookie_file:
        opts["cookiefile"] = cookie_file

    if config and config.ytdl_user_agent:
        opts["http_headers"] = {"User-Agent": config.ytdl_user_agent}

    return opts


def _pick_best_stream_url(info: dict[str, Any]) -> Optional[str]:
    """Select the best direct audio stream URL from yt-dlp info dict."""
    if not info:
        return None

    # Check direct top-level URL
    direct_url = info.get("url")
    if direct_url and direct_url.startswith("http"):
        return direct_url

    formats = info.get("formats", [])
    if not formats:
        return None

    # Filter audio formats that contain an actual direct URL
    valid_audio_formats = [
        f for f in formats
        if (f.get("url") or f.get("manifest_url")) and (f.get("acodec") and f.get("acodec") != "none")
    ]

    if valid_audio_formats:
        # Prefer formats with highest bitrate / audio bitrate
        best = max(
            valid_audio_formats,
            key=lambda f: (f.get("abr", 0) or 0, f.get("tbr", 0) or 0),
        )
        return best.get("url") or best.get("manifest_url")

    # Fallback to any audio or video format with a valid URL
    any_valid = [f for f in formats if f.get("url") or f.get("manifest_url")]
    if any_valid:
        best = max(any_valid, key=lambda f: (f.get("tbr", 0) or 0))
        return best.get("url") or best.get("manifest_url")

    return None


async def get_stream_url(
    video_id: str,
    proxy: str = "",
    config: Optional[AudioConfig] = None,
    ydl_opts: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Extract direct audio-only stream URL for a YouTube video ID or URL with automatic fallback."""
    url = video_id if video_id.startswith("http") else f"https://youtu.be/{video_id}"
    options = build_ydl_options(config, proxy)
    if ydl_opts:
        options.update(ydl_opts)

    loop = asyncio.get_running_loop()

    def _extract() -> Optional[str]:
        # Strategy 1: Primary extraction with android client & webpage skip
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = _pick_best_stream_url(info)
                if stream_url:
                    return stream_url
        except Exception as exc:
            log.warning("Primary yt-dlp extract failed for %s: %s", video_id, exc)

        # Strategy 2: Fallback with web_embedded
        try:
            fallback_options = dict(options)
            fallback_options["extractor_args"] = {
                "youtube": {
                    "player_client": ["web_embedded", "android"],
                    "player_skip": ["webpage"],
                }
            }
            with yt_dlp.YoutubeDL(fallback_options) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = _pick_best_stream_url(info)
                if stream_url:
                    return stream_url
        except Exception as exc:
            log.warning("Fallback yt-dlp extract failed for %s: %s", video_id, exc)

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
