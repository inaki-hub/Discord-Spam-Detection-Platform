from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.collector.events import MessageEvent
from app.features.burst_detection import (
    BURST_MESSAGES_IN_10S,
    evaluate_temporal_signals,
)
from app.features.message_features import extract_message_features
from app.features.user_features import UserProfileStore


def test_evaluate_temporal_signals_normal():
    signals = evaluate_temporal_signals(1, 5)
    assert signals.burst_activity is False
    assert signals.signals == ()


def test_evaluate_temporal_signals_burst_10s():
    signals = evaluate_temporal_signals(BURST_MESSAGES_IN_10S, 0)
    assert signals.burst_activity is True
    assert "high_message_rate_10s" in signals.signals


def test_profile_burst_after_rapid_messages():
    store = UserProfileStore()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    profile = None

    for i in range(BURST_MESSAGES_IN_10S):
        event = MessageEvent(
            message_id=str(i),
            guild_id="g",
            channel_id="c",
            author_id="u",
            timestamp=base + timedelta(seconds=i),
            content=f"msg {i}",
            urls=(),
            attachments=(),
            mentions=(),
        )
        profile = store.update(event, extract_message_features(event))

    assert profile is not None
    assert profile.messages_last_10s == BURST_MESSAGES_IN_10S
    assert profile.burst_activity is True
    assert "high_message_rate_10s" in profile.temporal_signals


def test_profile_no_burst_when_spread_out():
    store = UserProfileStore()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    profile = None

    for i in range(BURST_MESSAGES_IN_10S):
        event = MessageEvent(
            message_id=str(i),
            guild_id="g",
            channel_id="c",
            author_id="u",
            timestamp=base + timedelta(minutes=i * 2),
            content=f"msg {i}",
            urls=(),
            attachments=(),
            mentions=(),
        )
        profile = store.update(event, extract_message_features(event))

    assert profile is not None
    assert profile.burst_activity is False
