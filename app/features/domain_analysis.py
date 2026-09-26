from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.features.url_utils import extract_domain

DOMAIN_RATE_WINDOW = timedelta(minutes=1)
REPEATED_DOMAIN_RATIO_THRESHOLD = 0.5
DOMAINS_PER_MINUTE_THRESHOLD = 5.0


@dataclass
class DomainTrackerState:
    domain_hits: dict[str, int] = field(default_factory=dict)
    total_domain_url_count: int = 0
    repeated_domain_url_count: int = 0
    recent_domain_events: deque[tuple[datetime, str]] = field(default_factory=deque)


@dataclass(frozen=True)
class DomainMetrics:
    unique_domains: int
    repeated_domain_ratio: float
    domains_per_minute: float
    repeated_domain: bool
    domain_signals: tuple[str, ...]

    def to_feature_dict(self) -> dict:
        return {
            "unique_domains": self.unique_domains,
            "repeated_domain_ratio": round(self.repeated_domain_ratio, 4),
            "domains_per_minute": round(self.domains_per_minute, 2),
            "repeated_domain": self.repeated_domain,
            "domain_signals": list(self.domain_signals),
        }


def domains_from_urls(urls: tuple[str, ...]) -> tuple[str, ...]:
    domains: list[str] = []
    for url in urls:
        domain = extract_domain(url)
        if domain:
            domains.append(domain)
    return tuple(domains)


def observe_domains(
    state: DomainTrackerState,
    timestamp: datetime,
    urls: tuple[str, ...],
) -> DomainMetrics:
    ts = _ensure_utc(timestamp)
    message_domains = domains_from_urls(urls)

    for domain in message_domains:
        previous = state.domain_hits.get(domain, 0)
        if previous >= 1:
            state.repeated_domain_url_count += 1
        state.domain_hits[domain] = previous + 1
        state.total_domain_url_count += 1
        state.recent_domain_events.append((ts, domain))

    _prune_domain_events(state, ts)

    ratio = (
        state.repeated_domain_url_count / state.total_domain_url_count
        if state.total_domain_url_count
        else 0.0
    )
    per_minute = _domains_per_minute(state, ts)
    signals = _domain_signals(ratio, per_minute, message_domains, state.domain_hits)

    return DomainMetrics(
        unique_domains=len(state.domain_hits),
        repeated_domain_ratio=ratio,
        domains_per_minute=per_minute,
        repeated_domain=bool(signals),
        domain_signals=signals,
    )


def _prune_domain_events(state: DomainTrackerState, reference: datetime) -> None:
    cutoff = reference - DOMAIN_RATE_WINDOW
    while state.recent_domain_events and state.recent_domain_events[0][0] < cutoff:
        state.recent_domain_events.popleft()


def _domains_per_minute(state: DomainTrackerState, reference: datetime) -> float:
    cutoff = reference - DOMAIN_RATE_WINDOW
    count = sum(1 for ts, _ in state.recent_domain_events if ts >= cutoff)
    return float(count)


def _domain_signals(
    ratio: float,
    per_minute: float,
    message_domains: tuple[str, ...],
    domain_hits: dict[str, int],
) -> tuple[str, ...]:
    signals: list[str] = []
    if ratio >= REPEATED_DOMAIN_RATIO_THRESHOLD and domain_hits:
        signals.append("repeated_domain_ratio")
    if per_minute >= DOMAINS_PER_MINUTE_THRESHOLD:
        signals.append("high_domains_per_minute")
    if message_domains and all(domain_hits.get(d, 0) > 1 for d in set(message_domains)):
        signals.append("repeated_domain_in_message")
    return tuple(dict.fromkeys(signals))


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)
