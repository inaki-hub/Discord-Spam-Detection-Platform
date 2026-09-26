from __future__ import annotations

from datetime import datetime, timezone

from app.detection.automation_detector import AutomationDetector
from app.features.user_features import UserProfile


def _profile(**overrides) -> UserProfile:
    base = dict(
        user_id="u",
        guild_id="g",
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        total_messages=10,
        messages_last_10s=1,
        messages_last_60s=5,
        messages_last_10m=10,
        unique_channels=1,
        unique_domains=1,
        url_count=0,
        duplicate_message_count=0,
        repeated_content_count=0,
        repeated_content_interval=None,
        average_message_length=10.0,
        duplicate_ratio=0.0,
        spam_score=0,
        spam_classification="normal",
        automation_score=0,
        automation_classification="normal",
        regular_intervals=False,
        burst_activity=False,
        temporal_signals=(),
        max_similarity_to_recent=0.0,
        high_similarity_content=False,
        cross_channel_repetition=False,
        cross_channel_interval=None,
        cross_channel_signals=(),
        repeated_domain_ratio=0.0,
        domains_per_minute=0.0,
        repeated_domain=False,
        domain_signals=(),
    )
    base.update(overrides)
    return UserProfile(**base)


def test_automation_normal():
    result = AutomationDetector().evaluate(_profile())
    assert result.score == 0
    assert result.classification == "normal"


def test_automation_regular_and_burst():
    result = AutomationDetector().evaluate(
        _profile(regular_intervals=True, burst_activity=True)
    )
    assert result.score >= 60
    assert "regular_intervals" in result.signals
    assert "burst_activity" in result.signals


def test_automation_likely_combined():
    result = AutomationDetector().evaluate(
        _profile(
            regular_intervals=True,
            burst_activity=True,
            duplicate_ratio=0.5,
            repeated_content_count=4,
            messages_last_10s=10,
            unique_channels=3,
        )
    )
    assert result.classification == "automation_likely"
    assert result.score >= 70
