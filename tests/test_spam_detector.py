from __future__ import annotations

from datetime import datetime, timezone

from app.collector.events import MessageEvent
from app.detection.spam_detector import SpamDetector
from app.features.message_features import MessageFeatures
from app.features.user_features import UserProfile


def _profile(**overrides) -> UserProfile:
    base = dict(
        user_id="u",
        guild_id="g",
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        total_messages=5,
        messages_last_10s=1,
        messages_last_60s=3,
        messages_last_10m=5,
        unique_channels=1,
        unique_domains=1,
        url_count=2,
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


def test_spam_detector_normal():
    result = SpamDetector().evaluate(_profile())
    assert result.score == 0
    assert result.classification == "normal"
    assert result.signals == ()


def test_spam_detector_combined_signals():
    profile = _profile(
        burst_activity=True,
        cross_channel_repetition=True,
        repeated_domain=True,
        repeated_content_interval=5.0,
        temporal_signals=("high_message_rate_10s",),
    )
    result = SpamDetector().evaluate(profile)
    assert result.score >= 70
    assert result.classification == "spam_likely"
    assert "high_message_rate" in result.signals
    assert "cross_channel_repetition" in result.signals
    assert "repeated_domain" in result.signals
    assert "duplicate_content" in result.signals


def test_spam_detector_similar_content_single_signal():
    profile = _profile(high_similarity_content=True, max_similarity_to_recent=0.9)
    result = SpamDetector().evaluate(profile)
    assert result.score == 15
    assert result.classification == "normal"
    assert "similar_content" in result.signals


def test_spam_detector_with_message_features():
    profile = _profile(repeated_domain=True)
    features = MessageFeatures(
        length=100,
        word_count=20,
        url_count=4,
        mention_count=0,
        emoji_count=0,
        special_char_count=5,
        has_repetition=False,
        url_domains=("spam.test",),
        unique_url_count=4,
        content_hash="abc",
        normalized_preview="buy now",
    )
    result = SpamDetector().evaluate(profile, features)
    assert "repeated_domain" in result.signals
    assert "many_urls_in_message" in result.signals
