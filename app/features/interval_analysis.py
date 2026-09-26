from __future__ import annotations

import statistics
from dataclasses import dataclass

MIN_INTERVALS_FOR_REGULARITY = 4
REGULARITY_MAX_CV = 0.15
REGULARITY_MAX_MEAN_SECONDS = 180.0


@dataclass(frozen=True)
class IntervalMetrics:
    mean_seconds: float
    coefficient_of_variation: float
    regular_intervals: bool


def analyze_intervals(intervals: list[float]) -> IntervalMetrics:
    cleaned = [i for i in intervals if i > 0]
    if len(cleaned) < MIN_INTERVALS_FOR_REGULARITY:
        return IntervalMetrics(0.0, 0.0, False)

    mean = statistics.mean(cleaned)
    if mean <= 0:
        return IntervalMetrics(0.0, 0.0, False)

    cv = statistics.pstdev(cleaned) / mean
    regular = cv <= REGULARITY_MAX_CV and mean <= REGULARITY_MAX_MEAN_SECONDS
    return IntervalMetrics(mean, cv, regular)
