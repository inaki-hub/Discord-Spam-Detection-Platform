from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from app.detection.hybrid_config import HybridConfig
from app.detection.automation_detector import AutomationDetectionResult
from app.detection.hybrid import evaluate_hybrid
from app.detection.spam_detector import SpamDetectionResult
from app.features.user_features import UserProfile
from app.ml.prediction import MlPrediction


def _settings(**overrides) -> Settings:
    base = dict(
        discord_token="x",
        database_url="sqlite+aiosqlite:///./data/x.db",
        log_level="INFO",
        data_retention_days=0,
        alert_channels={},
        default_alert_channel="",
        raw_alert_channels="",
        ml_enabled=True,
        ml_model_path="",
        ml_hybrid_enabled=True,
        ml_score_boost_max=20,
        ml_alert_spam_threshold=0.85,
        ml_alert_automation_threshold=0.85,
        ml_hybrid_min_duplicate_ratio=0.25,
        moderation=_moderation_placeholder(),
        hybrid=HybridConfig(
            ml_hybrid_enabled=True,
            ml_score_boost_max=20,
            ml_alert_spam_threshold=0.85,
            ml_alert_automation_threshold=0.85,
            ml_hybrid_min_duplicate_ratio=0.25,
        ),
        mod_config_channel_id="",
    )
    base.update(overrides)
    return Settings(**base)


def _moderation_placeholder():
    from app.moderation.settings import ModerationSettings

    return ModerationSettings(
        enabled=False,
        dry_run=True,
        cooldown_seconds=300,
        penalize_spam=True,
        penalize_automation=False,
        min_effective_spam_score=40,
        min_effective_automation_score=40,
        timeout_spam_likely_seconds=0,
        timeout_suspicious_seconds=0,
        timeout_automation_likely_seconds=0,
        timeout_automation_suspicious_seconds=0,
    )


def _profile(**kwargs) -> UserProfile:
    now = datetime.now(timezone.utc)
    defaults = dict(
        user_id="u1",
        guild_id="g1",
        first_seen=now,
        last_seen=now,
        total_messages=30,
        messages_last_10s=2,
        messages_last_60s=10,
        messages_last_10m=30,
        unique_channels=2,
        unique_domains=0,
        url_count=0,
        duplicate_message_count=20,
        repeated_content_count=20,
        repeated_content_interval=0.3,
        average_message_length=2.0,
        duplicate_ratio=0.9,
        spam_score=0,
        spam_classification="normal",
        automation_score=0,
        automation_classification="normal",
        regular_intervals=False,
        burst_activity=False,
        temporal_signals=(),
        max_similarity_to_recent=1.0,
        high_similarity_content=False,
        cross_channel_repetition=True,
        cross_channel_interval=10.0,
        cross_channel_signals=("same_content_other_channel",),
        repeated_domain_ratio=0.0,
        domains_per_minute=0.0,
        repeated_domain=False,
        domain_signals=(),
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def test_boost_raises_effective_score():
    spam = SpamDetectionResult(30, "normal", ())
    auto = AutomationDetectionResult(10, "normal", ())
    ml = MlPrediction(spam_probability=0.9, automation_probability=0.1)
    out = evaluate_hybrid(spam, auto, _profile(), ml, _settings().hybrid)
    assert out.spam_boost == 18
    assert out.spam.score == 48
    assert out.spam.classification == "suspicious"


def test_ml_alert_when_rules_normal_but_high_probability_and_context():
    spam = SpamDetectionResult(25, "normal", ())
    auto = AutomationDetectionResult(15, "normal", ())
    ml = MlPrediction(spam_probability=0.95, automation_probability=0.05)
    out = evaluate_hybrid(spam, auto, _profile(), ml, _settings().hybrid)
    assert out.ml_alert_spam is True
    assert out.should_alert() is True
    assert "ml_high_spam_probability" in out.spam.signals


def test_hybrid_disabled_passthrough():
    spam = SpamDetectionResult(80, "spam_likely", ("duplicate_content",))
    auto = AutomationDetectionResult(0, "normal", ())
    ml = MlPrediction(0.99, 0.99)
    out = evaluate_hybrid(
        spam,
        auto,
        _profile(),
        ml,
        HybridConfig(
            ml_hybrid_enabled=False,
            ml_score_boost_max=20,
            ml_alert_spam_threshold=0.85,
            ml_alert_automation_threshold=0.85,
            ml_hybrid_min_duplicate_ratio=0.25,
        ),
    )
    assert out.spam.score == 80
    assert out.ml_spam_probability is None
