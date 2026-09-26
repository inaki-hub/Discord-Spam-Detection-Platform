from __future__ import annotations

DATASET_LABEL_UNKNOWN = "unknown"
DATASET_LABEL_NORMAL = "normal"
DATASET_LABEL_SPAM = "spam"
DATASET_LABEL_AUTOMATED_SPAM = "automated_spam"
DATASET_LABEL_LEGITIMATE_BOT = "legitimate_bot"

VALID_DATASET_LABELS: frozenset[str] = frozenset(
    {
        DATASET_LABEL_UNKNOWN,
        DATASET_LABEL_NORMAL,
        DATASET_LABEL_SPAM,
        DATASET_LABEL_AUTOMATED_SPAM,
        DATASET_LABEL_LEGITIMATE_BOT,
    }
)


def normalize_label(label: str) -> str:
    cleaned = label.strip().lower()
    if cleaned not in VALID_DATASET_LABELS:
        raise ValueError(
            f"Etiqueta inválida: {label!r}. Válidas: {sorted(VALID_DATASET_LABELS)}"
        )
    return cleaned
