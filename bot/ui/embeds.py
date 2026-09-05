"""Embed builders for Discord music bot responses with clean text formatting."""

from __future__ import annotations

from typing import Any, Optional

import discord

from bot.audio.queue import Queue, RepeatMode, Track
from bot.config import Config
from bot.utils.time import create_progress_bar, format_duration


def _get_default_config() -> Config:
    """Return a safe fallback Config instance for embed generation."""
    try:
        return Config()
    except Exception:
        from bot.config import DiscordConfig
        return Config(discord=DiscordConfig(bot_token="dummy", client_id="dummy"))


def nowplaying_embed(
    track: Track,
    state: Any = None,
    config: Optional[Config] = None,
    position_sec: int = 0,
) -> discord.Embed:
    """Build a clean 'Now Playing' embed with progress bar and playback details."""
    cfg = config or _get_default_config()
    color = cfg.ui.color_primary

    embed = discord.Embed(
        title="Now Playing",
        description=f"**[{track.display}]({track.url})**",
        color=color,
    )

    if track.thumbnail_url:
        embed.set_thumbnail(url=track.thumbnail_url)

    # Progress bar calculation
    total_sec = track.duration
    if total_sec > 0:
        bar = create_progress_bar(position_sec, total_sec, length=16)
        pos_str = format_duration(position_sec)
        dur_str = track.duration_str
        embed.add_field(
            name="Progress",
            value=f"`{pos_str}` {bar} `{dur_str}`",
            inline=False,
        )
    else:
        embed.add_field(
            name="Duration",
            value=f"`{track.duration_str}` (Live / Stream)",
            inline=True,
        )

    # Status chips
    if state:
        status_items = []
        if state.is_paused:
            status_items.append("Status: Paused")
        else:
            status_items.append("Status: Playing")

        if state.repeat_mode == RepeatMode.TRACK:
            status_items.append("Loop: Track")
        elif state.repeat_mode == RepeatMode.QUEUE:
            status_items.append("Loop: Queue")

        if getattr(state, "shuffle", False):
            status_items.append("Shuffle: On")

        vol_pct = int(getattr(state, "volume", 1.0) * 100)
        status_items.append(f"Volume: {vol_pct}%")

        if status_items:
            embed.add_field(
                name="Playback State",
                value=" | ".join(status_items),
                inline=False,
            )

    # Requester info in footer
    footer_text = ""
    if track.requester_name:
        footer_text = f"Requested by {track.requester_name}"
    elif track.requester_id:
        footer_text = f"Requested by <@{track.requester_id}>"

    if cfg.ui.footer_text:
        footer_text = f"{footer_text} | {cfg.ui.footer_text}" if footer_text else cfg.ui.footer_text

    if footer_text:
        embed.set_footer(text=footer_text)

    return embed


def queue_embed(
    queue: Queue,
    page: int = 0,
    per_page: int = 10,
    config: Optional[Config] = None,
) -> discord.Embed:
    """Build a paginated queue embed showing upcoming tracks and statistics."""
    cfg = config or _get_default_config()
    tracks = queue.all_tracks()
    total = len(tracks)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    embed = discord.Embed(
        title="Music Queue",
        color=cfg.ui.color_queue,
    )

    if total == 0 or queue.is_empty:
        embed.description = "The queue is currently empty. Add tracks using /play."
        footer = cfg.ui.footer_text or f"Add songs with {cfg.discord.command_prefix}play"
        embed.set_footer(text=footer)
        return embed

    current = queue.current
    if current:
        embed.description = (
            f"**Now Playing:**\n"
            f"[{current.display}]({current.url}) (`{current.duration_str}`)\n\n"
            f"**Up Next:**"
        )

    start = page * per_page
    end = min(start + per_page, total)

    if start < total:
        lines: list[str] = []
        for idx in range(start, end):
            t = tracks[idx]
            prefix = f"`#{idx + 1}`"
            active_marker = " [Playing]" if idx == queue.position else ""
            req_info = f" (<@{t.requester_id}>)" if t.requester_id else ""
            lines.append(f"{prefix} [{t.display}]({t.url}) `{t.duration_str}`{active_marker}{req_info}")
        embed.add_field(name="", value="\n".join(lines), inline=False)

    # Queue stats
    total_dur_str = format_duration(queue.total_duration)
    footer_str = f"Page {page + 1}/{total_pages} | {total} tracks in queue | Total time: {total_dur_str}"
    if cfg.ui.footer_text:
        footer_str += f" | {cfg.ui.footer_text}"
    embed.set_footer(text=footer_str)

    return embed


def search_embed(
    results: list[dict[str, Any]],
    query: str,
    config: Optional[Config] = None,
) -> discord.Embed:
    """Build a clean search results embed."""
    cfg = config or _get_default_config()
    embed = discord.Embed(
        title="Search Results",
        description=f"Results for: **{query}**\nSelect an option below to add to queue.",
        color=cfg.ui.color_primary,
    )

    if not results:
        embed.description = f"No results found for: `{query}`"
        return embed

    lines = []
    for idx, item in enumerate(results[:10], start=1):
        title = item.get("title", "Unknown")
        artists = item.get("artists", [])
        artist_name = artists[0]["name"] if artists and isinstance(artists[0], dict) else ""
        duration = item.get("duration", "")
        if not duration and "duration_seconds" in item:
            duration = format_duration(item["duration_seconds"])

        desc = f" - {artist_name}" if artist_name else ""
        dur_str = f" `[{duration}]`" if duration else ""
        lines.append(f"`{idx}.` **{title}**{desc}{dur_str}")

    embed.add_field(name="Top Matches", value="\n".join(lines), inline=False)
    return embed


def playlist_added_embed(
    title: str,
    count: int,
    total_duration: int,
    url: str = "",
    thumbnail_url: str = "",
    config: Optional[Config] = None,
) -> discord.Embed:
    """Build an embed when a playlist is added."""
    cfg = config or _get_default_config()
    dur_str = format_duration(total_duration)

    embed = discord.Embed(
        title="Playlist Added to Queue",
        description=f"**[{title}]({url})**" if url else f"**{title}**",
        color=cfg.ui.color_success,
    )
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    embed.add_field(name="Tracks Added", value=f"`{count}` tracks", inline=True)
    if total_duration > 0:
        embed.add_field(name="Total Duration", value=f"`{dur_str}`", inline=True)

    return embed


def error_embed(
    message: str,
    title: str = "Error",
    config: Optional[Config] = None,
) -> discord.Embed:
    """Build a standard error embed with configured styling."""
    cfg = config or _get_default_config()
    return discord.Embed(
        title=title,
        description=message,
        color=cfg.ui.color_error,
    )


def success_embed(
    message: str,
    title: str = "Success",
    config: Optional[Config] = None,
) -> discord.Embed:
    """Build a standard success embed with configured styling."""
    cfg = config or _get_default_config()
    return discord.Embed(
        title=title,
        description=message,
        color=cfg.ui.color_success,
    )


def warning_embed(
    message: str,
    title: str = "Warning",
    config: Optional[Config] = None,
) -> discord.Embed:
    """Build a warning embed with configured styling."""
    cfg = config or _get_default_config()
    return discord.Embed(
        title=title,
        description=message,
        color=cfg.ui.color_warning,
    )


def info_embed(
    message: str,
    title: str = "Information",
    config: Optional[Config] = None,
) -> discord.Embed:
    """Build an informational embed with configured styling."""
    cfg = config or _get_default_config()
    return discord.Embed(
        title=title,
        description=message,
        color=cfg.ui.color_primary,
    )
