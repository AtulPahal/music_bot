"""Audio source extraction via yt-dlp.

Fetches reliable direct audio stream URLs. Falls back gracefully
if extraction fails.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import yt_dlp

log = logging.getLogger(__name__)

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "default_search": "ytsearch",
}


async def get_stream_url(
    video_id: str,
    proxy: str = "",
    ydl_opts: Optional[dict] = None,
) -> Optional[str]:
    """Extract the best audio-only stream URL for a YouTube video.

    Args:
        video_id: YouTube video ID.
        proxy: Optional proxy URL (SOCKS5 or HTTP).
        ydl_opts: Optional overrides for yt-dlp options.

    Returns:
        Direct audio stream URL, or None if extraction fails.
    """
    url = f"https://youtu.be/{video_id}"
    options = dict(YDL_OPTIONS)
    if ydl_opts:
        options.update(ydl_opts)
    if proxy:
        options["proxy"] = proxy

    loop = asyncio.get_event_loop()

    def _extract() -> Optional[str]:
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as exc:
                log.warning("yt-dlp extract failed for %s: %s", video_id, exc)
                return None

        # Direct URL (single format)
        direct_url = info.get("url")
        if direct_url:
            return direct_url

        # Pick best audio-only format
        formats = info.get("formats", [])
        audio_formats = [f for f in formats if f.get("acodec") and f["acodec"] != "none"]
        if not audio_formats:
            audio_formats = formats  # fallback to any format

        if audio_formats:
            # Pick the one with highest bitrate among audio-only
            best = max(
                audio_formats,
                key=lambda f: f.get("tbr", 0) or 0,
            )
            stream_url = best.get("url") or best.get("manifest_url")
            if stream_url:
                return stream_url

        log.warning("No playable format found for %s", video_id)
        return None

    return await loop.run_in_executor(None, _extract)


async def extract_info(
    video_id: str,
    proxy: str = "",
    ydl_opts: Optional[dict] = None,
) -> Optional[dict]:
    """Extract full info dict for a video without downloading.

    Useful when you need metadata (title, duration, thumbnails, formats).
    """
    url = f"https://youtu.be/{video_id}"
    options = dict(YDL_OPTIONS)
    if ydl_opts:
        options.update(ydl_opts)
    if proxy:
        options["proxy"] = proxy

    loop = asyncio.get_event_loop()

    def _extract() -> Optional[dict]:
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except Exception as exc:
                log.warning("yt-dlp extract_info failed for %s: %s", video_id, exc)
                return None

    return await loop.run_in_executor(None, _extract)
