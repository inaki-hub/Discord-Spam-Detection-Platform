from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime

from app.collector.events import MessageEvent
from app.detection.automation_detector import AutomationDetectionResult
from app.detection.spam_detector import SpamDetectionResult

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.detection.hybrid import HybridEvaluation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    user_id: str
    guild_id: str
    channel_id: str
    timestamp: datetime
    spam_score: int
    automation_score: int
    spam_classification: str
    automation_classification: str
    signals: dict[str, list[str]]
    evidence: tuple[str, ...]
    spam_score_rules: int | None = None
    automation_score_rules: int | None = None
    ml_spam_probability: float | None = None
    ml_automation_probability: float | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_log_block(self) -> str:
        spam_signals = ", ".join(self.signals.get("spam", [])) or "-"
        auto_signals = ", ".join(self.signals.get("automation", [])) or "-"
        evidence = ", ".join(self.evidence) or "-"
        ml_line = ""
        if self.ml_spam_probability is not None:
            ml_line = (
                f"\nML spam_p: {self.ml_spam_probability:.3f} "
                f"auto_p: {self.ml_automation_probability or 0:.3f}"
            )
        rules_line = ""
        if self.spam_score_rules is not None:
            rules_line = (
                f"\nScores reglas (spam/auto): {self.spam_score_rules}/"
                f"{self.automation_score_rules}"
            )
        return (
            "[ALERT]\n"
            f"User: {self.user_id}\n"
            f"Guild: {self.guild_id}\n"
            f"Channel: {self.channel_id}\n"
            f"Timestamp: {self.timestamp.isoformat()}\n"
            f"Spam score: {self.spam_score}\n"
            f"Automation score: {self.automation_score}\n"
            f"Spam classification: {self.spam_classification}\n"
            f"Automation classification: {self.automation_classification}\n"
            f"Spam signals: {spam_signals}\n"
            f"Automation signals: {auto_signals}\n"
            f"Evidence: {evidence}"
            f"{rules_line}{ml_line}"
        )


class AlertManager:
    """Emite alertas explicables (v1: logs + persistencia local)."""

    def __init__(self, log: logging.Logger | None = None) -> None:
        self._log = log or logger

    def should_alert(
        self,
        spam: SpamDetectionResult,
        automation: AutomationDetectionResult,
    ) -> bool:
        return (
            spam.classification != "normal"
            or automation.classification != "normal"
        )

    def build(
        self,
        event: MessageEvent,
        spam: SpamDetectionResult,
        automation: AutomationDetectionResult,
        *,
        hybrid: "HybridEvaluation | None" = None,
    ) -> Alert:
        effective_spam = hybrid.spam if hybrid else spam
        effective_auto = hybrid.automation if hybrid else automation
        evidence = _collect_evidence(effective_spam, effective_auto)
        return Alert(
            user_id=event.author_id,
            guild_id=event.guild_id,
            channel_id=event.channel_id,
            timestamp=event.timestamp,
            spam_score=effective_spam.score,
            automation_score=effective_auto.score,
            spam_classification=effective_spam.classification,
            automation_classification=effective_auto.classification,
            signals={
                "spam": list(effective_spam.signals),
                "automation": list(effective_auto.signals),
            },
            evidence=evidence,
            spam_score_rules=hybrid.spam_rules.score if hybrid else None,
            automation_score_rules=hybrid.automation_rules.score if hybrid else None,
            ml_spam_probability=hybrid.ml_spam_probability if hybrid else None,
            ml_automation_probability=hybrid.ml_automation_probability if hybrid else None,
        )

    def emit(self, alert: Alert) -> None:
        self._log.warning(alert.to_log_block())


def _collect_evidence(
    spam: SpamDetectionResult,
    automation: AutomationDetectionResult,
) -> tuple[str, ...]:
    items: list[str] = []
    for name in spam.signals:
        items.append(f"spam:{name}")
    for name in automation.signals:
        items.append(f"automation:{name}")
    return tuple(dict.fromkeys(items))
