"""Unit tests for DatabaseService (PostgreSQL / Neon)."""

from __future__ import annotations

import pytest

from bot.audio.queue import Track
from bot.services.database import DatabaseService


class TestDatabaseService:
    def test_initial_state_not_connected(self):
        db = DatabaseService()
        assert not db.is_connected
        assert db.pool is None

    @pytest.mark.asyncio
    async def test_initialize_empty_url(self):
        db = DatabaseService()
        await db.initialize("")
        assert not db.is_connected

    @pytest.mark.asyncio
    async def test_disconnected_methods_safe_fallback(self):
        db = DatabaseService()
        # All methods should return empty results / False when offline rather than crashing
        assert await db.save_playlist(1, 2, "test", []) is False
        assert await db.get_playlist(1, "test") == []
        assert await db.list_playlists(1) == []
        assert await db.delete_playlist(1, "test") is False
        assert await db.get_db_history(1) == []
        # record_history should not raise
        await db.record_history(1, 2, "vid", "title")
        await db.close()
