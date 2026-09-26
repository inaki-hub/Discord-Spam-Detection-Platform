from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DuplicateObservation:
    """Resultado incremental al registrar un hash de contenido normalizado."""

    is_repeat: bool
    repeated_content_interval: float | None


def observe_content_hash(
    content_hash: str,
    timestamp: datetime,
    *,
    hash_occurrences: dict[str, int],
    hash_last_seen: dict[str, datetime],
) -> DuplicateObservation:
    """
    Registra un mensaje por hash normalizado.
    `repeated_content_interval` = segundos desde el mensaje anterior con el mismo hash.
    """
    previous_count = hash_occurrences.get(content_hash, 0)
    previous_ts = hash_last_seen.get(content_hash)
    is_repeat = previous_count >= 1

    interval: float | None = None
    if is_repeat and previous_ts is not None:
        interval = (timestamp - previous_ts).total_seconds()

    hash_occurrences[content_hash] = previous_count + 1
    hash_last_seen[content_hash] = timestamp

    return DuplicateObservation(is_repeat=is_repeat, repeated_content_interval=interval)


def duplicate_ratio(repeated_content_count: int, total_messages: int) -> float:
    if total_messages <= 0:
        return 0.0
    return repeated_content_count / total_messages
