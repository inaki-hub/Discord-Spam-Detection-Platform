from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HybridConfig:
    ml_hybrid_enabled: bool
    ml_score_boost_max: int
    ml_alert_spam_threshold: float
    ml_alert_automation_threshold: float
    ml_hybrid_min_duplicate_ratio: float
