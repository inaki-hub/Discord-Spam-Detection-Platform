from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass

from app.collector.events import MessageEvent
from app.features.url_utils import URL_PATTERN, extract_domain

_EMOJI_PATTERN = re.compile(
    r"<a?:\w+:\d+>|"
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E0-\U0001F1FF]+"
)
_SPECIAL_CHAR_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)


def normalize_message(content: str) -> str:
    """
    Normaliza contenido para comparación y hash.
    No modifica el texto original del evento; usar solo sobre una copia.
    """
    text = unicodedata.normalize("NFKC", content or "")
    text = text.lower()
    text = URL_PATTERN.sub(_replace_url_for_normalization, text)
    text = re.sub(r"[^\w\s<>:-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _replace_url_for_normalization(match: re.Match[str]) -> str:
    raw = match.group(0).rstrip(".,);]")
    domain = extract_domain(raw) or "unknown"
    safe_domain = domain.replace(".", "-")
    return f"<url:{safe_domain}>"


def normalized_content_hash(content: str) -> str:
    normalized = normalize_message(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _count_emojis(content: str) -> int:
    return len(_EMOJI_PATTERN.findall(content))


def _count_special_characters(content: str) -> int:
    return len(_SPECIAL_CHAR_PATTERN.findall(content))


def _has_internal_repetition(normalized: str) -> bool:
    if not normalized:
        return False
    words = _WORD_PATTERN.findall(normalized)
    if len(words) >= 2 and len(words) != len(set(words)):
        return True
    if re.search(r"(.)\1{4,}", normalized):
        return True
    return False


@dataclass(frozen=True)
class MessageFeatures:
    length: int
    word_count: int
    url_count: int
    mention_count: int
    emoji_count: int
    special_char_count: int
    has_repetition: bool
    url_domains: tuple[str, ...]
    unique_url_count: int
    content_hash: str
    normalized_preview: str
    max_similarity_to_recent: float = 0.0
    high_similarity_content: bool = False
    cross_channel_repetition: bool = False
    cross_channel_interval: float | None = None
    cross_channel_signals: tuple[str, ...] = ()
    repeated_domain_ratio: float = 0.0
    domains_per_minute: float = 0.0
    repeated_domain: bool = False
    domain_signals: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["cross_channel_signals"] = list(self.cross_channel_signals)
        data["domain_signals"] = list(self.domain_signals)
        return data


def with_similarity(features: MessageFeatures, result) -> MessageFeatures:
    from dataclasses import replace

    extra = result.to_feature_dict()
    return replace(
        features,
        max_similarity_to_recent=extra["max_similarity_to_recent"],
        high_similarity_content=extra["high_similarity_content"],
    )


def with_cross_channel(features: MessageFeatures, result) -> MessageFeatures:
    from dataclasses import replace

    extra = result.to_feature_dict()
    return replace(
        features,
        cross_channel_repetition=extra["cross_channel_repetition"],
        cross_channel_interval=extra["cross_channel_interval"],
        cross_channel_signals=tuple(extra["cross_channel_signals"]),
    )


def with_domain_metrics(features: MessageFeatures, metrics) -> MessageFeatures:
    from dataclasses import replace

    extra = metrics.to_feature_dict()
    return replace(
        features,
        repeated_domain_ratio=extra["repeated_domain_ratio"],
        domains_per_minute=extra["domains_per_minute"],
        repeated_domain=extra["repeated_domain"],
        domain_signals=tuple(extra["domain_signals"]),
    )


def extract_message_features(event: MessageEvent) -> MessageFeatures:
    content = event.content or ""
    normalized = normalize_message(content)
    domains: list[str] = []
    seen_domains: set[str] = set()
    for url in event.urls:
        domain = extract_domain(url)
        if domain and domain not in seen_domains:
            seen_domains.add(domain)
            domains.append(domain)

    unique_urls = len(set(event.urls))

    return MessageFeatures(
        length=len(content),
        word_count=len(_WORD_PATTERN.findall(content)),
        url_count=len(event.urls),
        mention_count=len(event.mentions),
        emoji_count=_count_emojis(content),
        special_char_count=_count_special_characters(content),
        has_repetition=_has_internal_repetition(normalized),
        url_domains=tuple(domains),
        unique_url_count=unique_urls,
        content_hash=normalized_content_hash(content),
        normalized_preview=normalized[:200],
    )
