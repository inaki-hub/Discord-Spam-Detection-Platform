from __future__ import annotations

from app.features.interval_analysis import analyze_intervals


def test_regular_intervals_detected():
    intervals = [2.0, 2.1, 1.9, 2.0, 2.05]
    metrics = analyze_intervals(intervals)
    assert metrics.regular_intervals is True
    assert metrics.coefficient_of_variation < 0.15


def test_irregular_intervals():
    metrics = analyze_intervals([1.0, 30.0, 2.0, 120.0, 5.0])
    assert metrics.regular_intervals is False
