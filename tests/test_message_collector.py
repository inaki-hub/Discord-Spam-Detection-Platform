from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.collector.message_collector import MessageCollector
from app.features.url_utils import extract_domain, extract_urls


def test_extract_urls_deduplicates():
    content = "Mira https://example.com y https://example.com/path"
    urls = extract_urls(content)
    assert len(urls) == 2
    assert "https://example.com" in urls


def test_extract_domain():
    assert extract_domain("https://www.Example.COM/foo") == "example.com"


def test_from_discord_message_ignores_dm():
    collector = MessageCollector()
    message = SimpleNamespace(
        guild=None,
        id=1,
        channel=SimpleNamespace(id=2),
        author=SimpleNamespace(id=3, bot=False),
        created_at=datetime.now(timezone.utc),
        content="hola",
        attachments=[],
        mentions=[],
    )
    assert collector.from_discord_message(message) is None  # type: ignore[arg-type]


def test_from_discord_message_builds_event():
    collector = MessageCollector()
    created = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    attachment = MagicMock()
    attachment.url = "https://cdn.discordapp.com/file.png"
    user = SimpleNamespace(id=999)
    message = SimpleNamespace(
        guild=SimpleNamespace(id=100),
        id=555,
        channel=SimpleNamespace(id=200),
        author=SimpleNamespace(id=300, bot=False),
        created_at=created,
        content="Visita https://spam.test promo",
        attachments=[attachment],
        mentions=[user],
    )
    event = collector.from_discord_message(message)  # type: ignore[arg-type]
    assert event is not None
    assert event.message_id == "555"
    assert event.guild_id == "100"
    assert event.channel_id == "200"
    assert event.author_id == "300"
    assert event.urls == ("https://spam.test",)
    assert event.attachments == ("https://cdn.discordapp.com/file.png",)
    assert event.mentions == ("999",)


def test_format_log_line():
    collector = MessageCollector()
    event = collector.from_discord_message(
        SimpleNamespace(
            guild=SimpleNamespace(id=1),
            id=2,
            channel=SimpleNamespace(id=3),
            author=SimpleNamespace(id=4, bot=False),
            created_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
            content="",
            attachments=[],
            mentions=[],
        )
    )
    assert event is not None
    line = collector.format_log_line(event)
    assert line.startswith("[MESSAGE]")
    assert "guild=1" in line
    assert "channel=3" in line
    assert "user=4" in line
    assert "timestamp=" in line
