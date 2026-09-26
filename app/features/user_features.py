from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from app.collector.events import MessageEvent
from app.features.burst_detection import evaluate_temporal_signals
from app.features.duplicate_detection import duplicate_ratio, observe_content_hash
from app.features.message_features import MessageFeatures
from app.features.cross_channel import (
    RECENT_CROSS_CHANNEL_MESSAGES,
    RecentChannelMessage,
    detect_cross_channel_repetition,
    prune_recent_messages,
)
from app.features.domain_analysis import DomainTrackerState, observe_domains
from app.features.interval_analysis import analyze_intervals
from app.features.message_similarity import compare_to_recent

WINDOW_10S = timedelta(seconds=10)
WINDOW_60S = timedelta(seconds=60)
WINDOW_10M = timedelta(minutes=10)


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    guild_id: str
    first_seen: datetime
    last_seen: datetime
    total_messages: int
    messages_last_10s: int
    messages_last_60s: int
    messages_last_10m: int
    unique_channels: int
    unique_domains: int
    url_count: int
    duplicate_message_count: int
    repeated_content_count: int
    repeated_content_interval: float | None
    average_message_length: float
    duplicate_ratio: float
    spam_score: int
    spam_classification: str
    automation_score: int
    automation_classification: str
    regular_intervals: bool
    burst_activity: bool
    temporal_signals: tuple[str, ...]
    max_similarity_to_recent: float
    high_similarity_content: bool
    cross_channel_repetition: bool
    cross_channel_interval: float | None
    cross_channel_signals: tuple[str, ...]
    repeated_domain_ratio: float
    domains_per_minute: float
    repeated_domain: bool
    domain_signals: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["first_seen"] = self.first_seen.isoformat()
        data["last_seen"] = self.last_seen.isoformat()
        data["temporal_signals"] = list(self.temporal_signals)
        data["cross_channel_signals"] = list(self.cross_channel_signals)
        data["domain_signals"] = list(self.domain_signals)
        return data


@dataclass
class _ProfileState:
    user_id: str
    guild_id: str
    first_seen: datetime
    last_seen: datetime
    total_messages: int = 0
    url_count: int = 0
    repeated_content_count: int = 0
    last_repeated_content_interval: float | None = None
    average_message_length: float = 0.0
    spam_score: int = 0
    spam_classification: str = "normal"
    automation_score: int = 0
    automation_classification: str = "normal"
    recent_intervals: list[float] = field(default_factory=list)
    last_regular_intervals: bool = False
    channels: set[str] = field(default_factory=set)
    domain_tracker: DomainTrackerState = field(default_factory=DomainTrackerState)
    hash_occurrences: dict[str, int] = field(default_factory=dict)
    hash_last_seen: dict[str, datetime] = field(default_factory=dict)
    recent_timestamps: deque[datetime] = field(default_factory=deque)
    recent_messages: list[RecentChannelMessage] = field(default_factory=list)
    last_similarity_max: float = 0.0
    last_high_similarity: bool = False
    last_cross_channel: bool = False
    last_cross_channel_interval: float | None = None
    last_cross_channel_signals: tuple[str, ...] = ()
    last_unique_domains: int = 0
    last_repeated_domain_ratio: float = 0.0
    last_domains_per_minute: float = 0.0
    last_repeated_domain: bool = False
    last_domain_signals: tuple[str, ...] = ()

    def snapshot(self) -> UserProfile:
        ratio = duplicate_ratio(self.repeated_content_count, self.total_messages)
        messages_last_10s = self._count_in_window(WINDOW_10S)
        messages_last_60s = self._count_in_window(WINDOW_60S)
        temporal = evaluate_temporal_signals(messages_last_10s, messages_last_60s)
        return UserProfile(
            user_id=self.user_id,
            guild_id=self.guild_id,
            first_seen=self.first_seen,
            last_seen=self.last_seen,
            total_messages=self.total_messages,
            messages_last_10s=messages_last_10s,
            messages_last_60s=messages_last_60s,
            messages_last_10m=self._count_in_window(WINDOW_10M),
            unique_channels=len(self.channels),
            unique_domains=self.last_unique_domains,
            url_count=self.url_count,
            duplicate_message_count=self.repeated_content_count,
            repeated_content_count=self.repeated_content_count,
            repeated_content_interval=self.last_repeated_content_interval,
            average_message_length=self.average_message_length,
            duplicate_ratio=ratio,
            spam_score=self.spam_score,
            spam_classification=self.spam_classification,
            automation_score=self.automation_score,
            automation_classification=self.automation_classification,
            regular_intervals=self.last_regular_intervals,
            burst_activity=temporal.burst_activity,
            temporal_signals=temporal.signals,
            max_similarity_to_recent=self.last_similarity_max,
            high_similarity_content=self.last_high_similarity,
            cross_channel_repetition=self.last_cross_channel,
            cross_channel_interval=self.last_cross_channel_interval,
            cross_channel_signals=self.last_cross_channel_signals,
            repeated_domain_ratio=self.last_repeated_domain_ratio,
            domains_per_minute=self.last_domains_per_minute,
            repeated_domain=self.last_repeated_domain,
            domain_signals=self.last_domain_signals,
        )

    def _prune_timestamps(self, reference: datetime) -> None:
        cutoff = reference - WINDOW_10M
        while self.recent_timestamps and self.recent_timestamps[0] < cutoff:
            self.recent_timestamps.popleft()

    def _count_in_window(self, window: timedelta) -> int:
        if not self.recent_timestamps:
            return 0
        reference = self.recent_timestamps[-1]
        threshold = reference - window
        return sum(1 for ts in self.recent_timestamps if ts >= threshold)


class UserProfileStore:
    """Perfiles por (guild_id, user_id), actualizados de forma incremental."""

    def __init__(self) -> None:
        self._states: dict[tuple[str, str], _ProfileState] = {}

    def update_with_similarity(self, event: MessageEvent, features: MessageFeatures):
        key = (event.guild_id, event.author_id)
        ts = _ensure_utc(event.timestamp)

        state = self._states.get(key)
        if state is None:
            state = _ProfileState(
                user_id=event.author_id,
                guild_id=event.guild_id,
                first_seen=ts,
                last_seen=ts,
            )
            self._states[key] = state

        state.last_seen = ts
        state.total_messages += 1
        state.channels.add(event.channel_id)
        state.url_count += features.url_count
        domain_metrics = observe_domains(state.domain_tracker, ts, event.urls)
        state.last_unique_domains = domain_metrics.unique_domains
        state.last_repeated_domain_ratio = domain_metrics.repeated_domain_ratio
        state.last_domains_per_minute = domain_metrics.domains_per_minute
        state.last_repeated_domain = domain_metrics.repeated_domain
        state.last_domain_signals = domain_metrics.domain_signals

        history_for_similarity = [
            (m.normalized, m.content_hash) for m in state.recent_messages
        ]
        similarity = compare_to_recent(
            features.normalized_preview,
            features.content_hash,
            history_for_similarity,
        )
        state.last_similarity_max = similarity.max_similarity
        state.last_high_similarity = similarity.high_similarity_content

        cross = detect_cross_channel_repetition(
            event.channel_id,
            ts,
            features.content_hash,
            features.normalized_preview,
            state.recent_messages,
        )
        state.last_cross_channel = cross.cross_channel_repetition
        state.last_cross_channel_interval = cross.cross_channel_interval
        state.last_cross_channel_signals = cross.signals

        dup = observe_content_hash(
            features.content_hash,
            ts,
            hash_occurrences=state.hash_occurrences,
            hash_last_seen=state.hash_last_seen,
        )
        if dup.is_repeat:
            state.repeated_content_count += 1
        state.last_repeated_content_interval = dup.repeated_content_interval

        n = state.total_messages
        state.average_message_length += (features.length - state.average_message_length) / n

        if state.recent_timestamps:
            delta = (ts - state.recent_timestamps[-1]).total_seconds()
            if delta > 0:
                state.recent_intervals.append(delta)
                if len(state.recent_intervals) > 20:
                    state.recent_intervals = state.recent_intervals[-20:]
                interval_metrics = analyze_intervals(state.recent_intervals)
                state.last_regular_intervals = interval_metrics.regular_intervals

        state._prune_timestamps(ts)
        state.recent_timestamps.append(ts)

        state.recent_messages.append(
            RecentChannelMessage(
                channel_id=event.channel_id,
                content_hash=features.content_hash,
                normalized=features.normalized_preview,
                timestamp=ts,
            )
        )
        state.recent_messages = prune_recent_messages(state.recent_messages, ts)
        if len(state.recent_messages) > RECENT_CROSS_CHANNEL_MESSAGES:
            state.recent_messages = state.recent_messages[-RECENT_CROSS_CHANNEL_MESSAGES:]

        return state.snapshot(), similarity, cross, domain_metrics

    def update(self, event: MessageEvent, features: MessageFeatures) -> UserProfile:
        profile, _, _, _ = self.update_with_similarity(event, features)
        return profile

    def get(self, guild_id: str, user_id: str) -> UserProfile | None:
        state = self._states.get((guild_id, user_id))
        if state is None:
            return None
        return state.snapshot()


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)
