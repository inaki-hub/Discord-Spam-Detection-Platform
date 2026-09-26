from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.collector.events import MessageEvent
from app.features.duplicate_detection import observe_content_hash
from app.features.message_features import extract_message_features
from app.features.user_features import UserProfileStore


def test_observe_content_hash_interval():
    ts1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = ts1 + timedelta(seconds=15)
    occurrences: dict[str, int] = {}
    last_seen: dict[str, datetime] = {}

    first = observe_content_hash("abc", ts1, hash_occurrences=occurrences, hash_last_seen=last_seen)
    second = observe_content_hash("abc", ts2, hash_occurrences=occurrences, hash_last_seen=last_seen)

    assert first.is_repeat is False
    assert first.repeated_content_interval is None
    assert second.is_repeat is True
    assert second.repeated_content_interval == 15.0
    assert occurrences["abc"] == 2


def test_profile_tracks_repeated_content():
    store = UserProfileStore()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def send(msg_id: str, offset_s: int, content: str):
        event = MessageEvent(
            message_id=msg_id,
            guild_id="g",
            channel_id="c",
            author_id="u",
            timestamp=base + timedelta(seconds=offset_s),
            content=content,
            urls=(),
            attachments=(),
            mentions=(),
        )
        return store.update(event, extract_message_features(event))

    p1 = send("1", 0, "promo link now")
    p2 = send("2", 5, "promo link now")
    p3 = send("3", 20, "promo link now")

    assert p1.repeated_content_count == 0
    assert p1.repeated_content_interval is None
    assert p2.repeated_content_count == 1
    assert p2.repeated_content_interval == 5.0
    assert p2.duplicate_ratio == 0.5
    assert p3.repeated_content_count == 2
    assert p3.repeated_content_interval == 15.0
    assert p3.duplicate_ratio == 2 / 3
