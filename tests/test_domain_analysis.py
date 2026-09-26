from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.collector.events import MessageEvent
from app.features.domain_analysis import DomainTrackerState, observe_domains
from app.features.message_features import extract_message_features
from app.features.user_features import UserProfileStore


def test_repeated_domain_ratio_incremental():
    state = DomainTrackerState()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    m1 = observe_domains(state, base, ("https://spam.test/a",))
    m2 = observe_domains(state, base + timedelta(seconds=10), ("https://spam.test/b",))
    m3 = observe_domains(state, base + timedelta(seconds=20), ("https://spam.test/c",))

    assert m1.unique_domains == 1
    assert m1.repeated_domain_ratio == 0.0
    assert m2.repeated_domain_ratio == 0.5
    assert m3.repeated_domain_ratio == 2 / 3
    assert m3.repeated_domain is True
    assert "repeated_domain_ratio" in m3.domain_signals


def test_domains_per_minute():
    state = DomainTrackerState()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    urls = ("https://a.com/1", "https://b.com/2")

    for i in range(3):
        metrics = observe_domains(state, base + timedelta(seconds=i * 5), urls)

    assert metrics.domains_per_minute == 6.0
    assert "high_domains_per_minute" in metrics.domain_signals


def test_profile_domain_metrics_via_store():
    store = UserProfileStore()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    e1 = MessageEvent(
        message_id="1",
        guild_id="g",
        channel_id="c",
        author_id="u",
        timestamp=base,
        content="link https://promo.example/x",
        urls=("https://promo.example/x",),
        attachments=(),
        mentions=(),
    )
    e2 = MessageEvent(
        message_id="2",
        guild_id="g",
        channel_id="c",
        author_id="u",
        timestamp=base + timedelta(seconds=8),
        content="otro https://promo.example/y",
        urls=("https://promo.example/y",),
        attachments=(),
        mentions=(),
    )

    store.update_with_similarity(e1, extract_message_features(e1))
    profile, _, _, domain = store.update_with_similarity(
        e2, extract_message_features(e2)
    )

    assert profile.unique_domains == 1
    assert profile.repeated_domain_ratio == 0.5
    assert domain.repeated_domain is True
