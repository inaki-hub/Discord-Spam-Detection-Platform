from __future__ import annotations

from app.dataset.records import DatasetSample


def vectorize_sample(sample: DatasetSample) -> dict[str, float]:
    """Convierte una muestra en features numéricas (nombres estables)."""
    row: dict[str, float] = {
        "rule_spam_score": float(sample.spam_score),
        "rule_automation_score": float(sample.automation_score),
    }
    _flatten_dict("msg_", sample.message_features, row)
    _flatten_dict("usr_", sample.user_features, row)
    _flatten_signals("sig_spam_", sample.detection_signals.get("spam") or [], row)
    _flatten_signals("sig_auto_", sample.detection_signals.get("automation") or [], row)
    return row


def vectorize_row(
    *,
    message_features: dict,
    user_features: dict,
    spam_score: int,
    automation_score: int,
    detection_signals: dict | None = None,
) -> dict[str, float]:
    signals = detection_signals or {}
    row: dict[str, float] = {
        "rule_spam_score": float(spam_score),
        "rule_automation_score": float(automation_score),
    }
    _flatten_dict("msg_", message_features, row)
    _flatten_dict("usr_", user_features, row)
    _flatten_signals("sig_spam_", signals.get("spam") or [], row)
    _flatten_signals("sig_auto_", signals.get("automation") or [], row)
    return row


def build_matrix(
    rows: list[dict[str, float]],
) -> tuple[list[str], list[list[float]]]:
    names = sorted({key for row in rows for key in row})
    matrix = [[row.get(name, 0.0) for name in names] for row in rows]
    return names, matrix


def _flatten_dict(prefix: str, data: dict, out: dict[str, float]) -> None:
    for key, value in data.items():
        name = f"{prefix}{key}"
        if isinstance(value, bool):
            out[name] = float(int(value))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out[name] = float(value)
        elif isinstance(value, list):
            out[f"{name}_len"] = float(len(value))


def _flatten_signals(prefix: str, signals: list[str], out: dict[str, float]) -> None:
    out[f"{prefix}count"] = float(len(signals))
    for signal in signals:
        out[f"{prefix}{signal}"] = 1.0
