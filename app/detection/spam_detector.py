from __future__ import annotations

from dataclasses import asdict, dataclass

from app.detection.scoring_weights import (
    SCORE_CROSS_CHANNEL_REPETITION,
    SCORE_DUPLICATE_CONTENT,
    SCORE_HIGH_DUPLICATE_RATIO,
    SCORE_HIGH_MESSAGE_RATE,
    SCORE_REPEATED_DOMAIN,
    SCORE_SIMILAR_CONTENT,
    classify_spam_score,
)
from app.features.message_features import MessageFeatures
from app.features.user_features import UserProfile

DUPLICATE_RATIO_MIN = 0.3


@dataclass(frozen=True)
class SpamDetectionResult:
    score: int
    classification: str
    signals: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["signals"] = list(self.signals)
        return data


class SpamDetector:
    """Motor de spam basado en reglas ponderadas sobre el perfil del usuario."""

    def evaluate(
        self,
        profile: UserProfile,
        features: MessageFeatures | None = None,
    ) -> SpamDetectionResult:
        weighted_signals: list[tuple[str, int]] = []

        if profile.burst_activity or profile.messages_last_10s >= 10:
            weighted_signals.append(("high_message_rate", SCORE_HIGH_MESSAGE_RATE))

        if profile.repeated_content_interval is not None:
            weighted_signals.append(("duplicate_content", SCORE_DUPLICATE_CONTENT))
        elif profile.duplicate_ratio >= DUPLICATE_RATIO_MIN:
            weighted_signals.append(("duplicate_content", SCORE_HIGH_DUPLICATE_RATIO))

        if profile.cross_channel_repetition:
            weighted_signals.append(
                ("cross_channel_repetition", SCORE_CROSS_CHANNEL_REPETITION)
            )

        if profile.repeated_domain:
            weighted_signals.append(("repeated_domain", SCORE_REPEATED_DOMAIN))

        if profile.high_similarity_content:
            weighted_signals.append(("similar_content", SCORE_SIMILAR_CONTENT))

        if features is not None and features.url_count >= 3:
            weighted_signals.append(("many_urls_in_message", SCORE_REPEATED_DOMAIN // 3))

        score = min(100, sum(weight for _, weight in weighted_signals))
        signal_names = tuple(name for name, _ in weighted_signals)
        classification = classify_spam_score(score)

        return SpamDetectionResult(
            score=score,
            classification=classification,
            signals=signal_names,
        )
