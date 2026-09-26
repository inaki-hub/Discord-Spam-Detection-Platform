from __future__ import annotations

from datetime import datetime, timezone

import discord

from app.collector.events import MessageEvent
from app.features.url_utils import extract_urls


class MessageCollector:
    """Transforma eventos de discord.py en MessageEvent internos."""

    def from_discord_message(self, message: discord.Message) -> MessageEvent | None:
        if message.guild is None:
            return None

        ts = message.created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        attachments = tuple(a.url for a in message.attachments)
        mentions = tuple(str(u.id) for u in message.mentions)
        content = message.content or ""

        return MessageEvent(
            message_id=str(message.id),
            guild_id=str(message.guild.id),
            channel_id=str(message.channel.id),
            author_id=str(message.author.id),
            timestamp=ts,
            content=content,
            urls=extract_urls(content),
            attachments=attachments,
            mentions=mentions,
        )

    def format_log_line(self, event: MessageEvent) -> str:
        ts = event.timestamp.isoformat()
        return (
            f"[MESSAGE]\n"
            f"guild={event.guild_id}\n"
            f"channel={event.channel_id}\n"
            f"user={event.author_id}\n"
            f"timestamp={ts}"
        )
