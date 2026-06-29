"""Queue data structures and RepeatMode for per-guild music queue."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RepeatMode(Enum):
    OFF = 0
    TRACK = 1
    QUEUE = 2


@dataclass
class Track:
    """Represents a single playable track."""

    video_id: str
    title: str
    artists: list[str] = field(default_factory=list)
    duration: int = 0
    thumbnail_url: str = ""
    stream_url: str = ""
    requester_id: int = 0
    source_url: str = ""  # original URL if provided

    @property
    def display(self) -> str:
        if self.artists:
            return f"{', '.join(self.artists)} - {self.title}"
        return self.title

    @property
    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.video_id}"

    @property
    def duration_str(self) -> str:
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


class Queue:
    """FIFO queue with position tracking, loop, shuffle, and history."""

    def __init__(self, max_length: int = 500) -> None:
        self._tracks: list[Track] = []
        self._position: int = 0
        self._repeat: RepeatMode = RepeatMode.OFF
        self._history: list[Track] = []
        self._max_length = max_length

    # --- Properties ---

    @property
    def current(self) -> Optional[Track]:
        if not self._tracks or self._position >= len(self._tracks):
            return None
        return self._tracks[self._position]

    @property
    def is_empty(self) -> bool:
        return len(self._tracks) == 0

    @property
    def is_full(self) -> bool:
        return len(self._tracks) >= self._max_length

    @property
    def length(self) -> int:
        return len(self._tracks)

    @property
    def position(self) -> int:
        return self._position

    @property
    def repeat_mode(self) -> RepeatMode:
        return self._repeat

    @repeat_mode.setter
    def repeat_mode(self, mode: RepeatMode) -> None:
        self._repeat = mode

    @property
    def upcoming(self) -> list[Track]:
        return self._tracks[self._position + 1 :]

    @property
    def history(self) -> list[Track]:
        return list(self._history)

    def all_tracks(self) -> list[Track]:
        """Return all tracks (for display)."""
        return list(self._tracks)

    # --- Mutations ---

    def add(self, track: Track, *, at_front: bool = False) -> bool:
        """Add a track to the queue. Returns False if queue is full."""
        if self.is_full:
            return False
        if at_front:
            insert_pos = min(self._position + 1, len(self._tracks))
            self._tracks.insert(insert_pos, track)
        else:
            self._tracks.append(track)
        return True

    def skip(self) -> Optional[Track]:
        """Advance to next track based on repeat mode."""
        self._history.append(self.current)
        if self._repeat == RepeatMode.TRACK:
            return self.current  # same position, track repeats
        self._position += 1
        if self._position >= len(self._tracks):
            if self._repeat == RepeatMode.QUEUE:
                self._position = 0
            else:
                return None  # queue ended
        return self.current

    def remove(self, position: int) -> Optional[Track]:
        """Remove a track by absolute position."""
        if 0 <= position < len(self._tracks):
            removed = self._tracks.pop(position)
            if position < self._position:
                self._position -= 1
            return removed
        return None

    def move(self, from_pos: int, to_pos: int) -> bool:
        """Move a track from one position to another."""
        if not (0 <= from_pos < len(self._tracks) and 0 <= to_pos < len(self._tracks)):
            return False
        track = self._tracks.pop(from_pos)
        self._tracks.insert(to_pos, track)
        if from_pos == self._position:
            self._position = to_pos
        return True

    def shuffle(self) -> None:
        """Shuffle upcoming tracks (keeps current track in place)."""
        upcoming_slice = self._tracks[self._position + 1 :]
        random.shuffle(upcoming_slice)
        self._tracks = self._tracks[: self._position + 1] + upcoming_slice

    def clear(self) -> None:
        """Clear all upcoming tracks. Current track stays."""
        self._tracks = self._tracks[: self._position + 1]

    def go_back(self) -> Optional[Track]:
        """Go back to the previous track from history.

        The history track is inserted before the current position
        so it becomes the next playable track.
        """
        if not self._history:
            return None
        prev = self._history.pop()
        self._tracks.insert(self._position, prev)
        return prev

    def remove_duplicates(self) -> int:
        """Remove duplicate video_ids from upcoming tracks. Returns count removed."""
        seen = {self._tracks[self._position].video_id} if self._tracks else set()
        removed = 0
        new_upcoming: list[Track] = []
        for track in self._tracks[self._position + 1 :]:
            if track.video_id in seen:
                removed += 1
            else:
                seen.add(track.video_id)
                new_upcoming.append(track)
        self._tracks = self._tracks[: self._position + 1] + new_upcoming
        return removed

    def set_position_by_track(self, track: Track) -> bool:
        """Set position to the given track (for queue jumps)."""
        try:
            idx = self._tracks.index(track)
            self._position = idx
            return True
        except ValueError:
            return False
