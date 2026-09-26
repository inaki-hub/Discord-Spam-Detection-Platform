from __future__ import annotations

from dataclasses import asdict, dataclass

from app.detection.scoring_weights import (
    classify_automation_score,
    SCORE_AUTOMATION_BURST,
    SCORE_FAST_ACTIVITY,
    SCORE_MULTI_CHANNEL_ACTIVITY,
    SCORE_REGULAR_INTERVALS,
    SCORE_REPETITIVE_PATTERN,
)
from app.features.user_features import UserProfile

FAST_MESSAGES_10S = 8
MULTI_CHANNEL_MIN = 2


@dataclass(frozen=True)
class AutomationDetectionResult:
    score: int
    classification: str
    signals: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["signals"] = list(self.signals)
        return data


class AutomationDetector:
    """Detecta patrones compatibles con automatización (independiente del spam)."""

    def evaluate(self, profile: UserProfile) -> AutomationDetectionResult:
        weighted: list[tuple[str, int]] = []

        if profile.regular_intervals:
            weighted.append(("regular_intervals", SCORE_REGULAR_INTERVALS))

        if profile.burst_activity:
            weighted.append(("burst_activity", SCORE_AUTOMATION_BURST))

        if profile.duplicate_ratio >= 0.4 or profile.repeated_content_count >= 3:
            weighted.append(("repetitive_pattern", SCORE_REPETITIVE_PATTERN))

        if (
            profile.messages_last_10s >= FAST_MESSAGES_10S
            and profile.unique_channels >= MULTI_CHANNEL_MIN
        ):
            weighted.append(("multi_channel_activity", SCORE_MULTI_CHANNEL_ACTIVITY))
        elif profile.messages_last_10s >= FAST_MESSAGES_10S:
            weighted.append(("fast_activity", SCORE_FAST_ACTIVITY))

        score = min(100, sum(w for _, w in weighted))
        signals = tuple(name for name, _ in weighted)
        return AutomationDetectionResult(
            score=score,
            classification=classify_automation_score(score),
            signals=signals,
        )
