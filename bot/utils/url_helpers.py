"""URL parsing and validation helpers for YouTube and YouTube Music."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

# Standard YouTube 11-character video ID pattern
VIDEO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# YouTube URL regex patterns
YOUTUBE_URL_PATTERNS = [
    # https://www.youtube.com/watch?v=VIDEO_ID
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
    # https://youtu.be/VIDEO_ID
    r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
    # https://music.youtube.com/watch?v=VIDEO_ID
    r"(?:https?://)?music\.youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
    # https://www.youtube.com/shorts/VIDEO_ID
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    # https://m.youtube.com/watch?v=VIDEO_ID
    r"(?:https?://)?m\.youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
    # https://www.youtube.com/embed/VIDEO_ID
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    # https://www.youtube.com/v/VIDEO_ID
    r"(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})",
]

# YouTube playlist regex patterns
PLAYLIST_PATTERNS = [
    r"(?:https?://)?(?:www\.|music\.)?youtube\.com/playlist\?.*list=([a-zA-Z0-9_-]+)",
    r"(?:https?://)?(?:www\.|music\.)?youtube\.com/watch\?.*list=([a-zA-Z0-9_-]+)",
]


def extract_video_id(url_or_query: str) -> Optional[str]:
    """Extract a YouTube video ID from a URL, or return the ID itself if bare."""
    if not url_or_query:
        return None
    clean = url_or_query.strip()
    if not clean:
        return None

    # Check for bare 11-char ID
    if "://" not in clean and not clean.startswith("www."):
        if VIDEO_ID_REGEX.match(clean):
            return clean
        return None

    for pattern in YOUTUBE_URL_PATTERNS:
        match = re.search(pattern, clean)
        if match:
            return match.group(1)

    # Fallback to urllib query parsing
    try:
        parsed = urlparse(clean)
        if "youtube.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            if "v" in qs and qs["v"] and VIDEO_ID_REGEX.match(qs["v"][0]):
                return qs["v"][0]
        elif "youtu.be" in parsed.netloc:
            path_id = parsed.path.strip("/")
            if VIDEO_ID_REGEX.match(path_id):
                return path_id
    except Exception:
        pass

    return None


def extract_playlist_id(url: str) -> Optional[str]:
    """Extract a playlist ID from a YouTube or YouTube Music URL."""
    if not url:
        return None
    clean = url.strip()

    for pattern in PLAYLIST_PATTERNS:
        match = re.search(pattern, clean)
        if match:
            playlist_id = match.group(1)
            # Ignore RD radio playlists for direct playlist fetching if bare query
            return playlist_id

    try:
        parsed = urlparse(clean)
        qs = parse_qs(parsed.query)
        if "list" in qs and qs["list"]:
            return qs["list"][0]
    except Exception:
        pass

    return None


def is_youtube_url(text: str) -> bool:
    """Check if the text represents any valid YouTube video or stream URL."""
    return extract_video_id(text) is not None or is_playlist_url(text)


def is_playlist_url(text: str) -> bool:
    """Check if the text represents a YouTube playlist URL."""
    return extract_playlist_id(text) is not None
