from __future__ import annotations

from app.detection.automation_detector import AutomationDetectionResult
from app.detection.hybrid import HybridEvaluation
from app.detection.spam_detector import SpamDetectionResult
from app.moderation.policy import decide_moderation
from app.moderation.settings import ModerationSettings


def _settings(**kwargs) -> ModerationSettings:
    base = dict(
        enabled=True,
        dry_run=True,
        cooldown_seconds=300,
        penalize_spam=True,
        penalize_automation=False,
        min_effective_spam_score=40,
        min_effective_automation_score=40,
        timeout_spam_likely_seconds=3600,
        timeout_suspicious_seconds=300,
        timeout_automation_likely_seconds=0,
        timeout_automation_suspicious_seconds=0,
    )
    base.update(kwargs)
    return ModerationSettings(**base)


def _hybrid(spam_score: int, spam_class: str, auto_score: int = 0, auto_class: str = "normal"):
    spam = SpamDetectionResult(spam_score, spam_class, ("duplicate_content",))
    auto = AutomationDetectionResult(auto_score, auto_class, ())
    return HybridEvaluation(
        spam=spam,
        automation=auto,
        spam_rules=spam,
        automation_rules=auto,
        ml_spam_probability=None,
        ml_automation_probability=None,
        spam_boost=0,
        automation_boost=0,
        ml_alert_spam=False,
        ml_alert_automation=False,
    )


def test_disabled_returns_none():
    assert decide_moderation(_hybrid(80, "spam_likely"), _settings(enabled=False)) is None


def test_suspicious_nuisance_timeout():
    decision = decide_moderation(_hybrid(45, "suspicious"), _settings())
    assert decision is not None
    assert decision.duration_seconds == 300
    assert "spam_suspicious" in decision.trigger


def test_below_min_score_no_action():
    assert decide_moderation(_hybrid(30, "suspicious"), _settings()) is None


def test_zero_timeout_skips():
    assert (
        decide_moderation(
            _hybrid(80, "spam_likely"),
            _settings(timeout_spam_likely_seconds=0, timeout_suspicious_seconds=0),
        )
        is None
    )
