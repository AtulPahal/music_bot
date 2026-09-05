"""Custom persistent playlist commands backed by Neon PostgreSQL storage."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from bot.ui.embeds import error_embed, info_embed, playlist_added_embed, success_embed
from bot.utils.checks import bot_has_voice_perms, in_voice, same_voice

if TYPE_CHECKING:
    from bot.bot import MusicBot

log = logging.getLogger(__name__)


class PlaylistCog(commands.Cog, name="Playlists"):
    """Manage and load custom server playlists stored in Neon PostgreSQL."""

    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    @property
    def player(self):
        cog = self.bot.get_cog("Music")
        return cog.player if cog else None

    @commands.hybrid_command(name="saveplaylist", aliases=["savepl"], description="Save the upcoming queue as a custom server playlist.")
    @in_voice()
    @same_voice()
    async def saveplaylist(self, ctx: commands.Context, *, name: str) -> None:
        """Save upcoming tracks to database."""
        if not self.bot.db or not self.bot.db.is_connected:
            await ctx.send(
                embed=error_embed(
                    "Database storage is not configured. Set DATABASE_URL in .env.",
                    config=self.bot.config,
                )
            )
            return

        if not self.player:
            return

        state = self.player.get_state(ctx.guild.id)
        if not state or state.queue.is_empty:
            await ctx.send(embed=error_embed("Queue is empty. Nothing to save.", config=self.bot.config))
            return

        tracks = state.queue.all_tracks()
        clean_name = name.strip()
        success = await self.bot.db.save_playlist(
            guild_id=ctx.guild.id,
            user_id=ctx.author.id,
            name=clean_name,
            tracks=tracks,
        )

        if success:
            await ctx.send(
                embed=success_embed(
                    f"Saved **{len(tracks)}** tracks to custom playlist **{clean_name}**.",
                    title="Playlist Saved",
                    config=self.bot.config,
                )
            )
        else:
            await ctx.send(embed=error_embed("Could not save playlist to database.", config=self.bot.config))

    @commands.hybrid_command(name="loadplaylist", aliases=["loadpl"], description="Load and queue a saved custom playlist from database.")
    @in_voice()
    @bot_has_voice_perms()
    async def loadplaylist(self, ctx: commands.Context, *, name: str) -> None:
        """Load and queue a saved playlist."""
        if not self.bot.db or not self.bot.db.is_connected:
            await ctx.send(
                embed=error_embed(
                    "Database storage is not configured. Set DATABASE_URL in .env.",
                    config=self.bot.config,
                )
            )
            return

        if not self.player:
            return

        clean_name = name.strip()
        tracks = await self.bot.db.get_playlist(ctx.guild.id, clean_name)
        if not tracks:
            await ctx.send(
                embed=error_embed(f"No saved playlist found with name: `{clean_name}`", config=self.bot.config)
            )
            return

        # Ensure bot is in voice channel
        joined, err = await self.player.join(ctx)
        if not joined:
            await ctx.send(embed=error_embed(err, config=self.bot.config))
            return

        added = await self.player.play_batch(ctx.guild.id, tracks)
        total_dur = sum(t.duration for t in tracks[:added])
        embed = playlist_added_embed(
            title=f"Custom Playlist: {clean_name}",
            count=added,
            total_duration=total_dur,
            config=self.bot.config,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="listplaylists", aliases=["listpl", "savedplaylists"], description="List all saved custom playlists.")
    async def listplaylists(self, ctx: commands.Context) -> None:
        """List all custom playlists saved for this server."""
        if not self.bot.db or not self.bot.db.is_connected:
            await ctx.send(
                embed=error_embed(
                    "Database storage is not configured. Set DATABASE_URL in .env.",
                    config=self.bot.config,
                )
            )
            return

        playlists = await self.bot.db.list_playlists(ctx.guild.id)
        if not playlists:
            await ctx.send(
                embed=info_embed(
                    "No custom playlists saved yet. Use `/saveplaylist <name>` to save one!",
                    title="Saved Playlists",
                    config=self.bot.config,
                )
            )
            return

        cfg = self.bot.config
        embed = discord.Embed(
            title="Custom Server Playlists",
            description=f"Found **{len(playlists)}** saved playlist(s). Use `/loadplaylist <name>` to play.",
            color=cfg.ui.color_primary,
        )

        lines = []
        for i, pl in enumerate(playlists, start=1):
            pl_name = pl.get("name", "Unknown")
            count = pl.get("track_count", 0)
            lines.append(f"`{i}.` **{pl_name}** (`{count}` tracks)")

        embed.add_field(name="Playlists", value="\n".join(lines), inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="deleteplaylist", aliases=["delpl"], description="Delete a saved custom playlist.")
    @in_voice()
    @same_voice()
    async def deleteplaylist(self, ctx: commands.Context, *, name: str) -> None:
        """Delete a saved playlist from database."""
        if not self.bot.db or not self.bot.db.is_connected:
            await ctx.send(
                embed=error_embed(
                    "Database storage is not configured. Set DATABASE_URL in .env.",
                    config=self.bot.config,
                )
            )
            return

        clean_name = name.strip()
        deleted = await self.bot.db.delete_playlist(ctx.guild.id, clean_name)
        if deleted:
            await ctx.send(
                embed=success_embed(
                    f"Deleted saved playlist **{clean_name}**.",
                    title="Playlist Deleted",
                    config=self.bot.config,
                )
            )
        else:
            await ctx.send(
                embed=error_embed(f"Could not find playlist `{clean_name}` to delete.", config=self.bot.config)
            )


async def setup(bot: "MusicBot") -> None:
    await bot.add_cog(PlaylistCog(bot))
