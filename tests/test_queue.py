"""Unit tests for Queue, Track, and RepeatMode."""

from __future__ import annotations

import pytest

from bot.audio.queue import Queue, RepeatMode, Track


@pytest.fixture
def sample_tracks() -> list[Track]:
    return [
        Track(video_id="abc123", title="Song A", artists=["Artist 1"], duration=180),
        Track(video_id="def456", title="Song B", artists=["Artist 2"], duration=240),
        Track(video_id="ghi789", title="Song C", artists=["Artist 3"], duration=200),
    ]


@pytest.fixture
def queue(sample_tracks) -> Queue:
    q = Queue(max_length=10)
    for t in sample_tracks:
        q.add(t)
    return q


class TestQueue:
    def test_add_and_length(self, queue):
        assert queue.length == 3
        assert not queue.is_empty

    def test_add_full(self, queue):
        q = Queue(max_length=2)
        q.add(Track(video_id="a", title="A"))
        q.add(Track(video_id="b", title="B"))
        assert not q.add(Track(video_id="c", title="C"))
        assert q.is_full

    def test_add_at_front(self, queue):
        new_track = Track(video_id="new", title="New")
        queue.add(new_track, at_front=True)
        upcoming = queue.upcoming
        assert upcoming[0].video_id == "new"

    def test_current(self, queue):
        assert queue.current is not None
        assert queue.current.video_id == "abc123"

    def test_current_empty(self):
        q = Queue()
        assert q.current is None

    def test_skip_advances(self, queue):
        queue.skip()
        assert queue.current is not None
        assert queue.current.video_id == "def456"  # now at position 1

    def test_skip_empty(self):
        q = Queue()
        assert q.skip() is None

    def test_skip_end_of_queue(self, queue):
        queue.skip()  # A → B
        queue.skip()  # B → C
        queue.skip()  # C → None
        assert queue.current is None

    def test_skip_track_loop(self, queue):
        queue.repeat_mode = RepeatMode.TRACK
        current_before = queue.current
        queue.skip()
        assert queue.current is not None
        assert queue.current.video_id == current_before.video_id  # same track

    def test_skip_queue_loop(self, queue):
        queue.repeat_mode = RepeatMode.QUEUE
        queue.skip()  # A → B
        queue.skip()  # B → C
        queue.skip()  # C → back to A
        assert queue.current is not None
        assert queue.current.video_id == "abc123"

    def test_remove_valid(self, queue):
        removed = queue.remove(0)
        assert removed is not None
        assert removed.video_id == "abc123"
        assert queue.length == 2

    def test_remove_invalid(self, queue):
        removed = queue.remove(99)
        assert removed is None

    def test_remove_tracks_before_current(self, queue):
        queue.skip()  # now at B (pos 1)
        removed = queue.remove(0)  # remove A
        assert removed is not None
        assert queue.position == 0  # adjusted
        assert queue.current.video_id == "def456"

    def test_move_valid(self, queue):
        assert queue.move(0, 2)
        tracks = queue.all_tracks()
        assert tracks[2].video_id == "abc123"

    def test_move_invalid(self, queue):
        assert not queue.move(0, 99)

    def test_shuffle(self, queue):
        original_order = [t.video_id for t in queue.all_tracks()]
        queue.shuffle()
        shuffled_order = [t.video_id for t in queue.all_tracks()]
        # Current track stays the same
        assert shuffled_order[0] == original_order[0]
        # Upcoming should be a permutation (possibly same if lucky)
        assert sorted(shuffled_order[1:]) == sorted(original_order[1:])

    def test_clear(self, queue):
        queue.clear()
        assert queue.length == 1  # current track stays
        assert queue.current is not None

    def test_remove_duplicates(self, queue):
        queue.add(Track(video_id="abc123", title="Dup A"))  # duplicate
        queue.add(Track(video_id="xyz999", title="Unique"))
        removed = queue.remove_duplicates()
        assert removed == 1
        upcoming_ids = [t.video_id for t in queue.upcoming]
        assert upcoming_ids.count("abc123") == 0
        assert "xyz999" in upcoming_ids

    def test_all_tracks(self, queue):
        all_t = queue.all_tracks()
        assert len(all_t) == 3

    def test_upcoming(self, queue):
        upcoming = queue.upcoming
        assert len(upcoming) == 2
        assert upcoming[0].video_id == "def456"

    def test_history(self, queue):
        queue.skip()
        queue.skip()
        assert len(queue.history) == 2
        assert queue.history[0].video_id == "abc123"

    def test_set_position_by_track(self, queue):
        # Use the exact same Track object from the queue
        track_c = queue.all_tracks()[2]
        assert queue.set_position_by_track(track_c)
        assert queue.current.video_id == "ghi789"

    def test_set_position_by_track_not_found(self, queue):
        fake = Track(video_id="nonexistent", title="Fake")
        assert not queue.set_position_by_track(fake)


class TestTrack:
    def test_display_with_artists(self):
        track = Track(video_id="a", title="Test", artists=["Artist One", "Artist Two"])
        assert "Artist One, Artist Two - Test" in track.display

    def test_display_without_artists(self):
        track = Track(video_id="a", title="Test")
        assert track.display == "Test"

    def test_url(self):
        track = Track(video_id="abc123def", title="Test")
        assert "abc123def" in track.url

    def test_duration_str_seconds(self):
        track = Track(video_id="a", title="T", duration=45)
        assert track.duration_str == "0:45"

    def test_duration_str_minutes(self):
        track = Track(video_id="a", title="T", duration=185)
        assert track.duration_str == "3:05"

    def test_duration_str_hours(self):
        track = Track(video_id="a", title="T", duration=3725)
        assert track.duration_str == "1:02:05"


class TestRepeatMode:
    def test_enum_values(self):
        assert RepeatMode.OFF.value == 0
        assert RepeatMode.TRACK.value == 1
        assert RepeatMode.QUEUE.value == 2
