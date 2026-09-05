"""Queue data structures, Track representation, and RepeatMode enumeration."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from bot.utils.time import format_duration


class RepeatMode(Enum):
    """Playback repeat modes."""

    OFF = 0
    TRACK = 1
    QUEUE = 2


@dataclass
class Track:
    """Represents a playable audio track with metadata."""

    video_id: str
    title: str
    artists: list[str] = field(default_factory=list)
    duration: int = 0
    thumbnail_url: str = ""
    stream_url: str = ""
    requester_id: int = 0
    requester_name: str = ""
    source_url: str = ""
    is_suggested: bool = False

    @property
    def artist_str(self) -> str:
        """Formatted comma-separated artist string."""
        return ", ".join(self.artists) if self.artists else ""

    @property
    def display(self) -> str:
        """Display string combining artists and title."""
        if self.artists:
            return f"{self.artist_str} - {self.title}"
        return self.title

    @property
    def url(self) -> str:
        """YouTube Music watch URL."""
        return f"https://music.youtube.com/watch?v={self.video_id}"

    @property
    def duration_str(self) -> str:
        """Formatted track duration (e.g. '03:45')."""
        return format_duration(self.duration)


class Queue:
    """Thread-safe FIFO music queue supporting loops, shuffle, history, and position jumping."""

    def __init__(self, max_length: int = 500) -> None:
        self._tracks: list[Track] = []
        self._position: int = 0
        self._repeat: RepeatMode = RepeatMode.OFF
        self._history: list[Track] = []
        self._max_length: int = max_length

    # --- Properties ---

    @property
    def current(self) -> Optional[Track]:
        """Currently active track."""
        if not self._tracks or self._position >= len(self._tracks) or self._position < 0:
            return None
        return self._tracks[self._position]

    @property
    def is_empty(self) -> bool:
        """Check if queue has any tracks."""
        return len(self._tracks) == 0

    @property
    def is_full(self) -> bool:
        """Check if queue reached max allowed capacity."""
        return len(self._tracks) >= self._max_length

    @property
    def length(self) -> int:
        """Total number of tracks in queue."""
        return len(self._tracks)

    @property
    def position(self) -> int:
        """Current track index (0-based)."""
        return self._position

    @property
    def repeat_mode(self) -> RepeatMode:
        """Current repeat mode."""
        return self._repeat

    @repeat_mode.setter
    def repeat_mode(self, mode: RepeatMode) -> None:
        self._repeat = mode

    @property
    def upcoming(self) -> list[Track]:
        """List of upcoming tracks after the current position."""
        if self._position + 1 >= len(self._tracks):
            return []
        return self._tracks[self._position + 1 :]

    @property
    def history(self) -> list[Track]:
        """List of previously played tracks."""
        return list(self._history)

    @property
    def total_duration(self) -> int:
        """Total duration of all remaining upcoming tracks in seconds."""
        return sum(t.duration for t in self.upcoming)

    def all_tracks(self) -> list[Track]:
        """Return a copy of all tracks in the queue."""
        return list(self._tracks)

    # --- Mutations ---

    def add(self, track: Track, *, at_front: bool = False) -> bool:
        """Add a single track to the queue. Returns False if queue is full."""
        if self.is_full:
            return False
        if at_front:
            insert_pos = min(self._position + 1, len(self._tracks))
            self._tracks.insert(insert_pos, track)
        else:
            self._tracks.append(track)
        return True

    def extend(self, tracks: list[Track]) -> int:
        """Add multiple tracks (e.g. from a playlist). Returns count of tracks added."""
        added = 0
        for track in tracks:
            if self.is_full:
                break
            self._tracks.append(track)
            added += 1
        return added

    def skip(self) -> Optional[Track]:
        """Advance playback according to the active repeat mode."""
        if self.current:
            self._history.append(self.current)

        if self._repeat == RepeatMode.TRACK:
            return self.current

        self._position += 1
        if self._position >= len(self._tracks):
            if self._repeat == RepeatMode.QUEUE and self._tracks:
                self._position = 0
                return self.current
            return None
        return self.current

    def jump_to(self, position: int) -> Optional[Track]:
        """Jump directly to a specific 0-based index."""
        if 0 <= position < len(self._tracks):
            if self.current:
                self._history.append(self.current)
            self._position = position
            return self.current
        return None

    def remove(self, position: int) -> Optional[Track]:
        """Remove a track by absolute index."""
        if 0 <= position < len(self._tracks):
            removed = self._tracks.pop(position)
            if position < self._position:
                self._position -= 1
            return removed
        return None

    def move(self, from_pos: int, to_pos: int) -> bool:
        """Move a track from one index to another."""
        if not (0 <= from_pos < len(self._tracks) and 0 <= to_pos < len(self._tracks)):
            return False
        track = self._tracks.pop(from_pos)
        self._tracks.insert(to_pos, track)
        if from_pos == self._position:
            self._position = to_pos
        elif from_pos < self._position <= to_pos:
            self._position -= 1
        elif to_pos <= self._position < from_pos:
            self._position += 1
        return True

    def shuffle(self) -> None:
        """Shuffle upcoming tracks while keeping current track intact."""
        if self._position + 1 < len(self._tracks):
            upcoming_slice = self._tracks[self._position + 1 :]
            random.shuffle(upcoming_slice)
            self._tracks = self._tracks[: self._position + 1] + upcoming_slice

    def clear(self) -> None:
        """Clear all upcoming tracks from queue."""
        if self._tracks:
            self._tracks = self._tracks[: self._position + 1]
        else:
            self._tracks = []
            self._position = 0

    def go_back(self) -> Optional[Track]:
        """Re-insert the last track from history into playback."""
        if not self._history:
            return None
        prev = self._history.pop()
        self._tracks.insert(self._position, prev)
        return prev

    def remove_duplicates(self) -> int:
        """Remove duplicate tracks from upcoming queue. Returns count removed."""
        seen = {self._tracks[self._position].video_id} if self._tracks and self.current else set()
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
        """Set queue position to the given track instance."""
        try:
            idx = self._tracks.index(track)
            self._position = idx
            return True
        except ValueError:
            return False
