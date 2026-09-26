from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.dataset.records import DatasetSample
from app.ml.advisor import MlAdvisor
from app.ml.features import vectorize_sample
from app.ml.targets import automation_binary_label, spam_binary_label
from app.ml.train import InsufficientDataError, train_models


def _sample(label: str, *, spam_score: int = 50, automation_score: int = 10) -> DatasetSample:
    return DatasetSample(
        message_id=f"msg-{label}-{spam_score}",
        guild_id="g1",
        channel_id="c1",
        user_id="u1",
        timestamp=datetime.now(timezone.utc),
        message_features={
            "length": 100,
            "word_count": 10,
            "url_count": 2,
            "has_repetition": label.startswith("spam"),
        },
        user_features={
            "total_messages": 5,
            "duplicate_ratio": 0.5 if "spam" in label else 0.0,
            "burst_activity": label == "automated_spam",
        },
        spam_score=spam_score,
        automation_score=automation_score,
        spam_classification="normal",
        automation_classification="normal",
        detection_signals={"spam": ["repeated_domain"] if spam_score > 40 else [], "automation": []},
        label=label,
    )


def test_label_mapping():
    assert spam_binary_label("spam") == 1
    assert spam_binary_label("normal") == 0
    assert spam_binary_label("unknown") is None
    assert automation_binary_label("legitimate_bot") == 1
    assert automation_binary_label("spam") == 0


def test_vectorize_includes_rule_scores():
    row = vectorize_sample(_sample("normal", spam_score=77))
    assert row["rule_spam_score"] == 77.0
    assert row["msg_length"] == 100.0


def test_train_requires_min_samples(tmp_path: Path):
    samples = [_sample("normal"), _sample("spam")]
    with pytest.raises(InsufficientDataError):
        train_models(samples, min_samples=20, model_path=tmp_path / "m.joblib")


def test_train_and_advisor_predict(tmp_path: Path):
    samples: list[DatasetSample] = []
    for i in range(12):
        samples.append(_sample("normal", spam_score=5 + i, automation_score=2))
    for i in range(12):
        samples.append(_sample("spam", spam_score=60 + i, automation_score=5))
    for i in range(12):
        samples.append(_sample("automated_spam", spam_score=80, automation_score=70 + i))
    for i in range(12):
        samples.append(_sample("legitimate_bot", spam_score=0, automation_score=40 + i))

    model_path = tmp_path / "bundle.joblib"
    result = train_models(samples, min_samples=20, model_path=model_path)
    assert model_path.is_file()
    assert result.spam_samples >= 20
    assert result.automation_samples >= 20

    advisor = MlAdvisor(model_path)
    assert advisor.enabled
    pred = advisor.predict(
        message_features={"length": 200, "word_count": 30, "url_count": 5, "has_repetition": True},
        user_features={"total_messages": 20, "duplicate_ratio": 0.9, "burst_activity": True},
        spam_score=85,
        automation_score=60,
        detection_signals={"spam": ["repeated_domain"], "automation": ["regular_intervals"]},
    )
    assert pred is not None
    assert 0.0 <= pred.spam_probability <= 1.0
    assert 0.0 <= pred.automation_probability <= 1.0
