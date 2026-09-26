from __future__ import annotations

from dataclasses import dataclass

from app.detection.hybrid import HybridEvaluation
from app.moderation.settings import ModerationSettings

MAX_TIMEOUT_SECONDS = 28 * 24 * 3600


@dataclass(frozen=True)
class ModerationDecision:
    duration_seconds: int
    reason: str
    trigger: str


def decide_moderation(
    hybrid: HybridEvaluation,
    settings: ModerationSettings,
) -> ModerationDecision | None:
    if not settings.enabled:
        return None

    duration = 0
    triggers: list[str] = []

    spam = hybrid.spam
    auto = hybrid.automation

    spam_ok = spam.score >= settings.min_effective_spam_score
    auto_ok = auto.score >= settings.min_effective_automation_score

    if settings.penalize_spam and spam_ok:
        if spam.classification == "spam_likely":
            duration = max(duration, settings.timeout_spam_likely_seconds)
            triggers.append("spam_likely")
        elif spam.classification == "suspicious":
            duration = max(duration, settings.timeout_suspicious_seconds)
            triggers.append("spam_suspicious")

    if settings.penalize_automation and auto_ok:
        if auto.classification == "automation_likely":
            duration = max(duration, settings.timeout_automation_likely_seconds)
            triggers.append("automation_likely")
        elif auto.classification == "automation_suspicious":
            duration = max(duration, settings.timeout_automation_suspicious_seconds)
            triggers.append("automation_suspicious")

    if duration <= 0:
        return None

    duration = min(duration, MAX_TIMEOUT_SECONDS)
    reason = (
        "Anti-spam (revisión automática): "
        + ", ".join(triggers)
        + f" · scores spam={spam.score} auto={auto.score}"
    )
    return ModerationDecision(
        duration_seconds=duration,
        reason=reason[:512],
        trigger=",".join(triggers),
    )
