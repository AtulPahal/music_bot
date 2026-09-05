"""Asynchronous PostgreSQL / Neon database service using asyncpg with connection pooling."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import asyncpg

from bot.audio.queue import Track

log = logging.getLogger(__name__)


class DatabaseService:
    """Async database service managing Neon PostgreSQL storage."""

    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None
        self._url: str = ""

    @property
    def is_connected(self) -> bool:
        """Check if connection pool is initialized and active."""
        return self.pool is not None

    async def initialize(self, database_url: str) -> None:
        """Connect to PostgreSQL / Neon with automatic SSL configuration."""
        if not database_url:
            log.info("No DATABASE_URL provided. Running without persistent database.")
            return

        self._url = database_url

        # Clean URL if necessary (e.g. pooler flags)
        clean_url = database_url
        if "channel_binding=" in clean_url:
            clean_url = clean_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "?")

        try:
            self.pool = await asyncpg.create_pool(
                clean_url,
                min_size=1,
                max_size=5,
                timeout=15.0,
                command_timeout=15.0,
                ssl="require" if ("neon.tech" in clean_url or "sslmode=require" in clean_url) else None,
            )
            log.info("Neon PostgreSQL connection pool initialized successfully.")
            await self._run_migrations()
        except Exception as e:
            log.warning("Could not connect to Neon database (%s). Running in memory mode.", e)
            self.pool = None

    async def _run_migrations(self) -> None:
        """Ensure required tables exist in database."""
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id BIGINT PRIMARY KEY,
                    volume DOUBLE PRECISION DEFAULT 0.5,
                    prefix TEXT DEFAULT '!',
                    repeat_mode INTEGER DEFAULT 0,
                    auto_disconnect_timeout INTEGER DEFAULT 300,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS saved_playlists (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    name TEXT NOT NULL,
                    tracks_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (guild_id, name)
                );
                CREATE TABLE IF NOT EXISTS playback_history (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration INTEGER,
                    played_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

    # --- Saved Playlists ---

    async def save_playlist(
        self,
        guild_id: int,
        user_id: int,
        name: str,
        tracks: list[Track],
    ) -> bool:
        """Save a list of tracks as a custom server playlist."""
        if not self.pool:
            return False

        data = [
            {
                "video_id": t.video_id,
                "title": t.title,
                "artists": t.artists,
                "duration": t.duration,
                "thumbnail_url": t.thumbnail_url,
                "source_url": t.source_url,
            }
            for t in tracks
        ]
        json_blob = json.dumps(data)

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO saved_playlists (guild_id, user_id, name, tracks_json, created_at)
                VALUES ($1, $2, $3, $4::jsonb, NOW())
                ON CONFLICT (guild_id, name)
                DO UPDATE SET tracks_json = $4::jsonb, created_at = NOW(), user_id = $2
                """,
                guild_id,
                user_id,
                name.lower().strip(),
                json_blob,
            )
        return True

    async def get_playlist(self, guild_id: int, name: str) -> list[Track]:
        """Fetch a saved custom playlist by name."""
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT tracks_json FROM saved_playlists WHERE guild_id = $1 AND name = $2",
                guild_id,
                name.lower().strip(),
            )
            if not row:
                return []

            raw = row["tracks_json"]
            items = json.loads(raw) if isinstance(raw, str) else raw
            tracks: list[Track] = []
            for item in items:
                tracks.append(
                    Track(
                        video_id=item.get("video_id", ""),
                        title=item.get("title", "Unknown"),
                        artists=item.get("artists", []),
                        duration=item.get("duration", 0),
                        thumbnail_url=item.get("thumbnail_url", ""),
                        source_url=item.get("source_url", ""),
                    )
                )
            return tracks

    async def list_playlists(self, guild_id: int) -> list[dict[str, Any]]:
        """List all saved playlists for a guild."""
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT name, jsonb_array_length(tracks_json) as track_count, created_at, user_id
                FROM saved_playlists
                WHERE guild_id = $1
                ORDER BY name ASC
                """,
                guild_id,
            )
            return [dict(r) for r in rows]

    async def delete_playlist(self, guild_id: int, name: str) -> bool:
        """Delete a saved custom playlist."""
        if not self.pool:
            return False

        async with self.pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM saved_playlists WHERE guild_id = $1 AND name = $2",
                guild_id,
                name.lower().strip(),
            )
            return "DELETE 1" in res

    # --- History & Analytics ---

    async def record_history(
        self,
        guild_id: int,
        user_id: int,
        video_id: str,
        title: str,
        artist: str = "",
        duration: int = 0,
    ) -> None:
        """Record track playback in persistent database history."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO playback_history (guild_id, user_id, video_id, title, artist, duration, played_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    """,
                    guild_id,
                    user_id,
                    video_id,
                    title,
                    artist,
                    duration,
                )
        except Exception as e:
            log.debug("Could not record database history: %s", e)

    async def get_db_history(self, guild_id: int, limit: int = 15) -> list[dict[str, Any]]:
        """Retrieve recent playback history from database."""
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT title, artist, duration, played_at
                FROM playback_history
                WHERE guild_id = $1
                ORDER BY played_at DESC
                LIMIT $2
                """,
                guild_id,
                limit,
            )
            return [dict(r) for r in rows]

    async def close(self) -> None:
        """Close connection pool cleanly."""
        if self.pool:
            await self.pool.close()
            self.pool = None
