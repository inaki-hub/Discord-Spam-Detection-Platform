from __future__ import annotations

from app.dataset.labels import (
    DATASET_LABEL_AUTOMATED_SPAM,
    DATASET_LABEL_LEGITIMATE_BOT,
    DATASET_LABEL_NORMAL,
    DATASET_LABEL_SPAM,
    DATASET_LABEL_UNKNOWN,
)

SPAM_POSITIVE_LABELS = frozenset({DATASET_LABEL_SPAM, DATASET_LABEL_AUTOMATED_SPAM})
AUTOMATION_POSITIVE_LABELS = frozenset(
    {DATASET_LABEL_AUTOMATED_SPAM, DATASET_LABEL_LEGITIMATE_BOT}
)


def spam_binary_label(label: str) -> int | None:
    """1 = spam, 0 = no spam; None si unknown o no usable."""
    cleaned = label.strip().lower()
    if cleaned == DATASET_LABEL_UNKNOWN:
        return None
    if cleaned in SPAM_POSITIVE_LABELS:
        return 1
    if cleaned in {DATASET_LABEL_NORMAL, DATASET_LABEL_LEGITIMATE_BOT}:
        return 0
    return None


def automation_binary_label(label: str) -> int | None:
    """1 = automatizado (spam o bot legítimo), 0 = humano."""
    cleaned = label.strip().lower()
    if cleaned == DATASET_LABEL_UNKNOWN:
        return None
    if cleaned in AUTOMATION_POSITIVE_LABELS:
        return 1
    if cleaned in {DATASET_LABEL_NORMAL, DATASET_LABEL_SPAM}:
        return 0
    return None
