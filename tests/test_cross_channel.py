from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.collector.events import MessageEvent
from app.features.cross_channel import RecentChannelMessage, detect_cross_channel_repetition
from app.features.message_features import extract_message_features
from app.features.user_features import UserProfileStore


def test_detect_cross_channel_same_hash():
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    store = UserProfileStore()

    e1 = MessageEvent(
        message_id="1",
        guild_id="g",
        channel_id="general",
        author_id="u",
        timestamp=base,
        content="Gana dinero aqui",
        urls=(),
        attachments=(),
        mentions=(),
    )
    e2 = MessageEvent(
        message_id="2",
        guild_id="g",
        channel_id="gaming",
        author_id="u",
        timestamp=base + timedelta(minutes=2),
        content="Gana dinero aqui",
        urls=(),
        attachments=(),
        mentions=(),
    )

    store.update_with_similarity(e1, extract_message_features(e1))
    _, _, cross, _ = store.update_with_similarity(e2, extract_message_features(e2))

    assert cross.cross_channel_repetition is True
    assert cross.cross_channel_interval == 120.0
    assert "same_content_other_channel" in cross.signals


def test_no_cross_channel_same_channel_repeat():
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    store = UserProfileStore()
    content = "solo en un canal"

    for i in range(2):
        event = MessageEvent(
            message_id=str(i),
            guild_id="g",
            channel_id="general",
            author_id="u",
            timestamp=base + timedelta(seconds=i * 5),
            content=content,
            urls=(),
            attachments=(),
            mentions=(),
        )
        _, _, cross, _ = store.update_with_similarity(event, extract_message_features(event))

    assert cross.cross_channel_repetition is False


def test_cross_channel_outside_window_ignored():
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    history = [
        RecentChannelMessage(
            channel_id="a",
            content_hash="hash1",
            normalized="promo spam",
            timestamp=base,
        )
    ]
    result = detect_cross_channel_repetition(
        channel_id="b",
        timestamp=base + timedelta(minutes=11),
        content_hash="hash1",
        normalized="promo spam",
        history=history,
    )
    assert result.cross_channel_repetition is False
