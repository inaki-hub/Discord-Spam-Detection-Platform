from __future__ import annotations

from datetime import datetime, timezone

from app.collector.events import MessageEvent
from app.features.message_features import (
    extract_message_features,
    normalize_message,
    normalized_content_hash,
)


def test_normalize_message_collapses_similar_phrases():
    a = normalize_message("VISITA MI WEB")
    b = normalize_message("Visita mi web!")
    c = normalize_message("visita   mi   web")
    assert a == b == c


def test_normalize_message_urls_by_domain():
    a = normalize_message("mira https://Example.COM/x")
    b = normalize_message("mira https://www.example.com/y")
    assert a == b == "mira <url:example-com>"


def test_normalized_hash_stable():
    h1 = normalized_content_hash("Hola   mundo")
    h2 = normalized_content_hash("hola mundo")
    assert h1 == h2


def test_extract_message_features():
    event = MessageEvent(
        message_id="1",
        guild_id="g",
        channel_id="c",
        author_id="u",
        timestamp=datetime.now(timezone.utc),
        content="Visita https://spam.test y https://spam.test/path !!!!",
        urls=("https://spam.test", "https://spam.test/path"),
        attachments=(),
        mentions=("99", "100"),
    )
    features = extract_message_features(event)
    assert features.length > 0
    assert features.word_count >= 3
    assert features.url_count == 2
    assert features.unique_url_count == 2
    assert features.mention_count == 2
    assert features.url_domains == ("spam.test",)
    assert len(features.content_hash) == 64
    assert features.special_char_count >= 1


def test_has_repetition_detects_duplicate_words():
    event = MessageEvent(
        message_id="2",
        guild_id="g",
        channel_id="c",
        author_id="u",
        timestamp=datetime.now(timezone.utc),
        content="spam spam spam offer",
        urls=(),
        attachments=(),
        mentions=(),
    )
    features = extract_message_features(event)
    assert features.has_repetition is True
