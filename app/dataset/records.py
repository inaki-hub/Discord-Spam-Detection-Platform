from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.collector.events import MessageEvent
from app.dataset.labels import DATASET_LABEL_UNKNOWN
from app.detection.automation_detector import AutomationDetectionResult
from app.detection.spam_detector import SpamDetectionResult
from app.features.message_features import MessageFeatures
from app.features.user_features import UserProfile


@dataclass(frozen=True)
class DatasetSample:
    message_id: str
    guild_id: str
    channel_id: str
    user_id: str
    timestamp: datetime
    message_features: dict
    user_features: dict
    spam_score: int
    automation_score: int
    spam_classification: str
    automation_classification: str
    detection_signals: dict[str, list[str]]
    label: str = DATASET_LABEL_UNKNOWN

    def to_export_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "message_features": self.message_features,
            "user_features": self.user_features,
            "spam_score": self.spam_score,
            "automation_score": self.automation_score,
            "spam_classification": self.spam_classification,
            "automation_classification": self.automation_classification,
            "detection_signals": self.detection_signals,
            "label": self.label,
        }


def build_dataset_sample(
    event: MessageEvent,
    features: MessageFeatures,
    profile: UserProfile,
    spam: SpamDetectionResult,
    automation: AutomationDetectionResult,
) -> DatasetSample:
    return DatasetSample(
        message_id=event.message_id,
        guild_id=event.guild_id,
        channel_id=event.channel_id,
        user_id=event.author_id,
        timestamp=event.timestamp,
        message_features=features.to_dict(),
        user_features=profile.to_dict(),
        spam_score=spam.score,
        automation_score=automation.score,
        spam_classification=spam.classification,
        automation_classification=automation.classification,
        detection_signals={
            "spam": list(spam.signals),
            "automation": list(automation.signals),
        },
    )
