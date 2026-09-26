from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MlPrediction:
    spam_probability: float
    automation_probability: float
