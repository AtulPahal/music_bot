"""Time formatting utilities."""

from __future__ import annotations


def format_duration(seconds: int) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_duration(text: str) -> int:
    """Parse a duration string like '1:30' or '1:23:45' to seconds."""
    parts = list(map(int, text.split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] if parts else 0
