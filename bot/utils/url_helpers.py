"""URL parsing helpers for extracting YouTube video IDs."""

from __future__ import annotations

import re
from typing import Optional

# Patterns for various YouTube URL formats
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
]


def extract_video_id(url_or_query: str) -> Optional[str]:
    """Extract a YouTube video ID from a URL, or the ID itself if bare."""
    if not url_or_query or "://" not in url_or_query and not url_or_query.startswith("www."):
        if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_query):
            return url_or_query
        return None

    for pattern in YOUTUBE_URL_PATTERNS:
        match = re.search(pattern, url_or_query)
        if match:
            return match.group(1)
    return None


def is_youtube_url(text: str) -> bool:
    """Check if the text looks like a YouTube URL."""
    return extract_video_id(text) is not None
