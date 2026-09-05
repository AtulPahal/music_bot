"""Generic and queue-specific paginated views with clean text navigation controls."""

from __future__ import annotations

import logging
from typing import Optional

import discord

from bot.audio.queue import Queue
from bot.config import Config
from bot.ui.embeds import queue_embed

log = logging.getLogger(__name__)


class QueuePaginator(discord.ui.View):
    """Paginated view for displaying the music queue with clear text navigation controls."""

    def __init__(
        self,
        queue: Queue,
        config: Optional[Config] = None,
        per_page: Optional[int] = None,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.queue = queue
        if config:
            self.config = config
        else:
            try:
                self.config = Config()
            except Exception:
                from bot.config import DiscordConfig
                self.config = Config(discord=DiscordConfig(bot_token="dummy", client_id="dummy"))
        self.per_page = per_page or self.config.ui.queue_page_size
        self.current_page = 0
        self._message: Optional[discord.Message] = None

        self._update_button_states()

    @property
    def total_pages(self) -> int:
        total = len(self.queue.all_tracks())
        return max(1, (total + self.per_page - 1) // self.per_page)

    def _update_button_states(self) -> None:
        is_first = self.current_page <= 0
        is_last = self.current_page >= self.total_pages - 1

        self.first_button.disabled = is_first
        self.prev_button.disabled = is_first
        self.next_button.disabled = is_last
        self.last_button.disabled = is_last

    async def _update_view(self, interaction: discord.Interaction) -> None:
        self._update_button_states()
        embed = queue_embed(
            self.queue,
            page=self.current_page,
            per_page=self.per_page,
            config=self.config,
        )
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.button(label="First", style=discord.ButtonStyle.secondary, custom_id="q_first", row=0)
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = 0
        await self._update_view(interaction)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, custom_id="q_prev", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page > 0:
            self.current_page -= 1
        await self._update_view(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="q_next", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        await self._update_view(interaction)

    @discord.ui.button(label="Last", style=discord.ButtonStyle.secondary, custom_id="q_last", row=0)
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = max(0, self.total_pages - 1)
        await self._update_view(interaction)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="q_close", row=0)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        try:
            await interaction.response.edit_message(view=None)
        except Exception:
            pass
        self.stop()

    async def on_timeout(self) -> None:
        if self._message:
            try:
                await self._message.edit(view=None)
            except Exception:
                pass
        self.stop()
