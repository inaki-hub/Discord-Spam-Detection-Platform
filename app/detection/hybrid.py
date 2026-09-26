from __future__ import annotations

from dataclasses import dataclass

from app.detection.hybrid_config import HybridConfig
from app.detection.automation_detector import AutomationDetectionResult
from app.detection.scoring_weights import classify_automation_score, classify_spam_score
from app.detection.spam_detector import SpamDetectionResult
from app.features.user_features import UserProfile
from app.ml.prediction import MlPrediction


@dataclass(frozen=True)
class HybridEvaluation:
    """Scores/clasificaciones efectivos para alertas (reglas + ML opcional)."""

    spam: SpamDetectionResult
    automation: AutomationDetectionResult
    spam_rules: SpamDetectionResult
    automation_rules: AutomationDetectionResult
    ml_spam_probability: float | None
    ml_automation_probability: float | None
    spam_boost: int
    automation_boost: int
    ml_alert_spam: bool
    ml_alert_automation: bool

    def should_alert(self) -> bool:
        if self.spam.classification != "normal" or self.automation.classification != "normal":
            return True
        return self.ml_alert_spam or self.ml_alert_automation

    def hybrid_payload(self) -> dict:
        return {
            "spam_score_rules": self.spam_rules.score,
            "automation_score_rules": self.automation_rules.score,
            "spam_score_effective": self.spam.score,
            "automation_score_effective": self.automation.score,
            "spam_boost": self.spam_boost,
            "automation_boost": self.automation_boost,
            "ml_alert_spam": self.ml_alert_spam,
            "ml_alert_automation": self.ml_alert_automation,
        }


def evaluate_hybrid(
    spam: SpamDetectionResult,
    automation: AutomationDetectionResult,
    profile: UserProfile,
    ml: MlPrediction | None,
    config: HybridConfig,
) -> HybridEvaluation:
    if not config.ml_hybrid_enabled or ml is None:
        return HybridEvaluation(
            spam=spam,
            automation=automation,
            spam_rules=spam,
            automation_rules=automation,
            ml_spam_probability=None,
            ml_automation_probability=None,
            spam_boost=0,
            automation_boost=0,
            ml_alert_spam=False,
            ml_alert_automation=False,
        )

    spam_boost = int(round(config.ml_score_boost_max * ml.spam_probability))
    auto_boost = int(round(config.ml_score_boost_max * ml.automation_probability))
    eff_spam_score = min(100, spam.score + spam_boost)
    eff_auto_score = min(100, automation.score + auto_boost)

    spam_signals = list(spam.signals)
    auto_signals = list(automation.signals)

    ml_alert_spam = (
        spam.classification == "normal"
        and ml.spam_probability >= config.ml_alert_spam_threshold
        and _spam_context(profile, config)
    )
    ml_alert_auto = (
        automation.classification == "normal"
        and ml.automation_probability >= config.ml_alert_automation_threshold
        and _automation_context(profile)
    )

    if ml_alert_spam and "ml_high_spam_probability" not in spam_signals:
        spam_signals.append("ml_high_spam_probability")
    if ml_alert_auto and "ml_high_automation_probability" not in auto_signals:
        auto_signals.append("ml_high_automation_probability")

    effective_spam = SpamDetectionResult(
        score=eff_spam_score,
        classification=classify_spam_score(eff_spam_score),
        signals=tuple(spam_signals),
    )
    effective_auto = AutomationDetectionResult(
        score=eff_auto_score,
        classification=classify_automation_score(eff_auto_score),
        signals=tuple(auto_signals),
    )

    return HybridEvaluation(
        spam=effective_spam,
        automation=effective_auto,
        spam_rules=spam,
        automation_rules=automation,
        ml_spam_probability=ml.spam_probability,
        ml_automation_probability=ml.automation_probability,
        spam_boost=spam_boost,
        automation_boost=auto_boost,
        ml_alert_spam=ml_alert_spam,
        ml_alert_automation=ml_alert_auto,
    )


def _spam_context(profile: UserProfile, config: HybridConfig) -> bool:
    return (
        profile.duplicate_ratio >= config.ml_hybrid_min_duplicate_ratio
        or profile.messages_last_60s >= 5
        or profile.repeated_content_count >= 3
        or profile.cross_channel_repetition
    )


def _automation_context(profile: UserProfile) -> bool:
    return (
        profile.burst_activity
        or profile.messages_last_10s >= 8
        or profile.regular_intervals
        or profile.unique_channels >= 2
    )
