"""Time formatting and visual progress bar utilities."""

from __future__ import annotations


def format_duration(seconds: int) -> str:
    """Convert integer seconds to standard HH:MM:SS or MM:SS format.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string (e.g. '03:45' or '1:12:30').
    """
    if seconds < 0:
        seconds = 0
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_duration(text: str) -> int:
    """Parse a duration string like '1:30', '03:45', or '1:23:45' into seconds.

    Args:
        text: Duration string to parse.

    Returns:
        Duration in seconds, or 0 if unparseable.
    """
    if not text:
        return 0
    clean = text.strip()
    if clean.isdigit():
        return int(clean)
    try:
        parts = [int(p) for p in clean.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:
            return parts[0]
    except (ValueError, TypeError):
        pass
    return 0


def create_progress_bar(
    current: int,
    total: int,
    length: int = 15,
    filled_char: str = "=",
    empty_char: str = "-",
    indicator: str = "o",
) -> str:
    """Create a visual text progress bar for audio playback using plain text characters.

    Args:
        current: Current playback position in seconds.
        total: Total track duration in seconds.
        length: Length of progress bar in character units.
        filled_char: Character for the elapsed portion.
        empty_char: Character for the remaining portion.
        indicator: Current position marker.

    Returns:
        Rendered progress bar string (e.g. '[====o----------]').
    """
    if length < 3:
        length = 3
    inner_len = length - 2  # account for brackets '[' and ']'

    if total <= 0:
        return f"[{indicator}{empty_char * (inner_len - 1)}]"

    fraction = max(0.0, min(1.0, current / total))
    pos = int(fraction * (inner_len - 1))
    bar = (
        filled_char * pos
        + indicator
        + empty_char * (inner_len - 1 - pos)
    )
    return f"[{bar}]"
