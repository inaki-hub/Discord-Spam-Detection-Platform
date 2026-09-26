from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.collector.events import MessageEvent
from app.features.message_features import extract_message_features
from app.features.message_similarity import (
    HIGH_SIMILARITY_THRESHOLD,
    text_similarity,
)
from app.features.user_features import UserProfileStore


def test_text_similarity_close_paraphrase():
    a = "visita mi pagina para ganar dinero"
    b = "visita mi página y gana dinero"
    sim = text_similarity(a, b)
    assert sim >= HIGH_SIMILARITY_THRESHOLD


def test_text_similarity_different_messages():
    sim = text_similarity("hola que tal", "compra cripto ahora")
    assert sim < HIGH_SIMILARITY_THRESHOLD


def test_profile_high_similarity_not_exact_duplicate():
    store = UserProfileStore()
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    e1 = MessageEvent(
        message_id="1",
        guild_id="g",
        channel_id="c",
        author_id="u",
        timestamp=base,
        content="Visita mi pagina para ganar dinero",
        urls=(),
        attachments=(),
        mentions=(),
    )
    e2 = MessageEvent(
        message_id="2",
        guild_id="g",
        channel_id="c",
        author_id="u",
        timestamp=base + timedelta(seconds=3),
        content="Visita mi página y gana dinero",
        urls=(),
        attachments=(),
        mentions=(),
    )

    p1, s1, _, _ = store.update_with_similarity(e1, extract_message_features(e1))
    p2, s2, _, _ = store.update_with_similarity(e2, extract_message_features(e2))

    assert p1.high_similarity_content is False
    assert s2.max_similarity >= HIGH_SIMILARITY_THRESHOLD
    assert p2.high_similarity_content is True
