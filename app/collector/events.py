from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MessageEvent:
    message_id: str
    guild_id: str
    channel_id: str
    author_id: str
    timestamp: datetime
    content: str
    urls: tuple[str, ...] = field(default_factory=tuple)
    attachments: tuple[str, ...] = field(default_factory=tuple)
    mentions: tuple[str, ...] = field(default_factory=tuple)
