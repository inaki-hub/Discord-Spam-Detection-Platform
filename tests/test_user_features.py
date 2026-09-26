from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.collector.events import MessageEvent
from app.features.message_features import extract_message_features
from app.features.user_features import UserProfileStore


def _event(
    msg_id: str,
    ts: datetime,
    *,
    guild: str = "g1",
    channel: str = "c1",
    author: str = "u1",
    content: str = "hello",
) -> MessageEvent:
    return MessageEvent(
        message_id=msg_id,
        guild_id=guild,
        channel_id=channel,
        author_id=author,
        timestamp=ts,
        content=content,
        urls=(),
        attachments=(),
        mentions=(),
    )


def test_profile_increments_incrementally():
    store = UserProfileStore()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    e1 = _event("1", base, content="aaa")
    p1 = store.update(e1, extract_message_features(e1))
    assert p1.total_messages == 1
    assert p1.average_message_length == 3.0
    assert p1.repeated_content_count == 0

    e2 = _event("2", base + timedelta(seconds=1), content="bbbb")
    p2 = store.update(e2, extract_message_features(e2))
    assert p2.total_messages == 2
    assert p2.average_message_length == 3.5


def test_duplicate_content_updates_ratio():
    store = UserProfileStore()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    e1 = _event("1", base, content="same text")
    e2 = _event("2", base + timedelta(seconds=2), content="same text")
    store.update(e1, extract_message_features(e1))
    p = store.update(e2, extract_message_features(e2))

    assert p.repeated_content_count == 1
    assert p.duplicate_message_count == 1
    assert p.duplicate_ratio == 0.5
    assert p.repeated_content_interval == 2.0


def test_time_windows_and_channels():
    store = UserProfileStore()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    events = [
        _event("1", base, channel="c1", content="one"),
        _event("2", base + timedelta(seconds=5), channel="c2", content="two"),
        _event("3", base + timedelta(seconds=8), channel="c2", content="three"),
    ]
    profile = None
    for ev in events:
        profile = store.update(ev, extract_message_features(ev))

    assert profile is not None
    assert profile.messages_last_10s == 3
    assert profile.messages_last_60s == 3
    assert profile.unique_channels == 2

    old = _event("4", base + timedelta(minutes=11), content="later")
    profile = store.update(old, extract_message_features(old))
    assert profile.messages_last_10m == 1
    assert profile.messages_last_10s == 1
