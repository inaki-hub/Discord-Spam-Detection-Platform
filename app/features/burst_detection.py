from __future__ import annotations

from dataclasses import dataclass

# Umbrales centralizados: generan señales, no clasifican spam por sí solos.
BURST_MESSAGES_IN_10S = 10
BURST_MESSAGES_IN_60S = 30


@dataclass(frozen=True)
class TemporalSignals:
    """Señales temporales derivadas de contadores por ventana."""

    burst_activity: bool
    signals: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "burst_activity": self.burst_activity,
            "signals": list(self.signals),
        }


def evaluate_temporal_signals(
    messages_last_10s: int,
    messages_last_60s: int,
) -> TemporalSignals:
    reasons: list[str] = []
    if messages_last_10s >= BURST_MESSAGES_IN_10S:
        reasons.append("high_message_rate_10s")
    if messages_last_60s >= BURST_MESSAGES_IN_60S:
        reasons.append("high_message_rate_60s")
    return TemporalSignals(
        burst_activity=bool(reasons),
        signals=tuple(reasons),
    )
