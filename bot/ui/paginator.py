"""Generic paginated view for multi-page embeds (e.g. queue display)."""

from __future__ import annotations

from typing import Optional

import discord

from bot.audio.queue import Queue
from bot.ui.embeds import queue_embed


class QueuePaginator(discord.ui.View):
    """Paginated view for displaying the music queue."""

    def __init__(self, queue: Queue, per_page: int = 10) -> None:
        super().__init__(timeout=60)
        self.queue = queue
        self.per_page = per_page
        self.current_page = 0
        self._message: Optional[discord.Message] = None

    @property
    def total_pages(self) -> int:
        total = len(self.queue.all_tracks())
        return max(1, (total + self.per_page - 1) // self.per_page)

    def _update_button_states(self) -> None:
        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    async def _update(self, interaction: discord.Interaction) -> None:
        self._update_button_states()
        embed = queue_embed(self.queue, page=self.current_page, per_page=self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.secondary, custom_id="queue_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page > 0:
            self.current_page -= 1
        await self._update(interaction)

    @discord.ui.button(label=">", style=discord.ButtonStyle.secondary, custom_id="queue_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        await self._update(interaction)

    @discord.ui.button(label="X", style=discord.ButtonStyle.danger, custom_id="queue_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(view=None)
        self.stop()

    async def on_timeout(self) -> None:
        if self._message:
            try:
                await self._message.edit(view=None)
            except Exception:
                pass
        self.stop()
