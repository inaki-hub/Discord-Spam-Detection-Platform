from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.features.message_similarity import HIGH_SIMILARITY_THRESHOLD, text_similarity

CROSS_CHANNEL_WINDOW = timedelta(minutes=10)
RECENT_CROSS_CHANNEL_MESSAGES = 30


@dataclass(frozen=True)
class RecentChannelMessage:
    channel_id: str
    content_hash: str
    normalized: str
    timestamp: datetime


@dataclass(frozen=True)
class CrossChannelResult:
    cross_channel_repetition: bool
    cross_channel_interval: float | None
    signals: tuple[str, ...]

    def to_feature_dict(self) -> dict:
        return {
            "cross_channel_repetition": self.cross_channel_repetition,
            "cross_channel_interval": self.cross_channel_interval,
            "cross_channel_signals": list(self.signals),
        }


def prune_recent_messages(
    messages: list[RecentChannelMessage],
    reference: datetime,
) -> list[RecentChannelMessage]:
    cutoff = reference - CROSS_CHANNEL_WINDOW
    return [m for m in messages if m.timestamp >= cutoff]


def detect_cross_channel_repetition(
    channel_id: str,
    timestamp: datetime,
    content_hash: str,
    normalized: str,
    history: list[RecentChannelMessage],
) -> CrossChannelResult:
    ts = _ensure_utc(timestamp)
    signals: list[str] = []
    best_interval: float | None = None

    for prev in history:
        if prev.channel_id == channel_id:
            continue
        age = ts - _ensure_utc(prev.timestamp)
        if age > CROSS_CHANNEL_WINDOW or age < timedelta(0):
            continue

        interval = age.total_seconds()
        matched = False
        if prev.content_hash == content_hash:
            signals.append("same_content_other_channel")
            matched = True
        elif text_similarity(normalized, prev.normalized) >= HIGH_SIMILARITY_THRESHOLD:
            signals.append("similar_content_other_channel")
            matched = True

        if matched and (best_interval is None or interval < best_interval):
            best_interval = interval

    unique_signals = tuple(dict.fromkeys(signals))
    return CrossChannelResult(
        cross_channel_repetition=bool(unique_signals),
        cross_channel_interval=best_interval,
        signals=unique_signals,
    )


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)
