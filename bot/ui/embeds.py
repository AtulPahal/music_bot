"""Embed builders for music bot responses."""

from __future__ import annotations

from typing import Optional

import discord

from bot.audio.queue import Queue, Track


def nowplaying_embed(track: Track, state) -> discord.Embed:
    """Build a 'Now Playing' embed for the current track."""
    duration = track.duration_str

    embed = discord.Embed(
        title="Now Playing",
        description=f"[{track.display}]({track.url})",
        color=discord.Color.green(),
    )
    if track.thumbnail_url:
        embed.set_thumbnail(url=track.thumbnail_url)
    embed.add_field(name="Duration", value=duration)

    if state:
        status = []
        if state.is_paused:
            status.append("Paused")
        if state.repeat_mode.value == 1:
            status.append("Track Loop")
        elif state.repeat_mode.value == 2:
            status.append("Queue Loop")
        if state.shuffle:
            status.append("Shuffle")
        if status:
            embed.add_field(name="Status", value=" | ".join(status), inline=False)

    return embed


def queue_embed(queue: Queue, page: int = 0, per_page: int = 10) -> discord.Embed:
    """Build a paginated queue embed."""
    tracks = queue.all_tracks()
    current_pos = queue.position
    total = len(tracks)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    embed = discord.Embed(
        title="Music Queue",
        color=discord.Color.blue(),
    )

    if total == 0:
        embed.description = "The queue is empty."
        embed.set_footer(text="Add songs with /play")
        return embed

    current = queue.current
    if current:
        icon = ">" if not hasattr(queue, '_paused') else "||"
        embed.description = (
            f"**Now Playing:**\n"
            f"{icon} [{current.display}]({current.url}) `{current.duration_str}`\n\n"
        )

    start = page * per_page
    end = min(start + per_page, total)

    if start < total:
        lines = []
        for i in range(start, end):
            track = tracks[i]
            marker = " <" if i == current_pos else ""
            lines.append(
                f"`{i + 1}.` [{track.display}]({track.url}) `{track.duration_str}`{marker}"
            )
        embed.add_field(name="Upcoming", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Page {page + 1}/{total_pages} * {total} tracks")

    return embed


def search_embed(results: list[dict], query: str) -> discord.Embed:
    """Build a search results embed."""
    embed = discord.Embed(
        title=f"Search Results: {query}",
        color=discord.Color.purple(),
    )

    if not results:
        embed.description = "No results found."
        return embed

    lines = []
    for i, r in enumerate(results[:10]):
        title = r.get("title", "Unknown")
        result_type = r.get("resultType", "song")
        duration = ""
        if "duration" in r:
            duration = f" `{r['duration']}`"
        elif "duration_seconds" in r:
            m, s = divmod(r["duration_seconds"], 60)
            duration = f" `{m}:{s:02d}`"

        lines.append(f"`{i + 1}.` **{title}** ({result_type}){duration}")

    if lines:
        embed.description = "\n".join(lines)

    return embed


def error_embed(message: str, title: str = "Error") -> discord.Embed:
    """Build a simple error embed."""
    embed = discord.Embed(
        title=title,
        description=message,
        color=discord.Color.red(),
    )
    return embed


def success_embed(message: str, title: str = "Success") -> discord.Embed:
    """Build a simple success embed."""
    embed = discord.Embed(
        title=title,
        description=message,
        color=discord.Color.green(),
    )
    return embed
