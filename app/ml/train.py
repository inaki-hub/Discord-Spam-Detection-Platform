from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import DATA_DIR, ensure_data_dir
from app.dataset.records import DatasetSample
from app.ml.features import build_matrix, vectorize_sample
from app.ml.targets import automation_binary_label, spam_binary_label

DEFAULT_MODEL_PATH = DATA_DIR / "models" / "ml_bundle.joblib"
BUNDLE_VERSION = 1


@dataclass(frozen=True)
class TrainResult:
    model_path: Path
    spam_samples: int
    automation_samples: int
    metrics: dict[str, dict[str, float | None]]


class InsufficientDataError(ValueError):
    pass


def train_models(
    samples: list[DatasetSample],
    *,
    min_samples: int = 20,
    model_path: Path | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> TrainResult:
    spam_X, spam_y = _prepare_task(samples, spam_binary_label)
    auto_X, auto_y = _prepare_task(samples, automation_binary_label)

    if len(spam_y) < min_samples:
        raise InsufficientDataError(
            f"Spam: hacen falta al menos {min_samples} muestras etiquetadas "
            f"(spam/automated_spam vs normal/legitimate_bot); hay {len(spam_y)}."
        )
    if len(auto_y) < min_samples:
        raise InsufficientDataError(
            f"Automation: hacen falta al menos {min_samples} muestras etiquetadas "
            f"(automated_spam/legitimate_bot vs normal/spam); hay {len(auto_y)}."
        )

    spam_pipeline, spam_metrics, spam_feature_names = _fit_binary(
        spam_X, spam_y, test_size, random_state
    )
    auto_pipeline, auto_metrics, auto_feature_names = _fit_binary(
        auto_X, auto_y, test_size, random_state
    )

    out_path = model_path or DEFAULT_MODEL_PATH
    ensure_data_dir()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bundle = {
        "version": BUNDLE_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "spam_feature_names": spam_feature_names,
        "automation_feature_names": auto_feature_names,
        "spam_pipeline": spam_pipeline,
        "automation_pipeline": auto_pipeline,
        "metrics": {"spam": spam_metrics, "automation": auto_metrics},
    }
    joblib.dump(bundle, out_path)

    return TrainResult(
        model_path=out_path,
        spam_samples=len(spam_y),
        automation_samples=len(auto_y),
        metrics=bundle["metrics"],
    )


def metrics_as_json(metrics: dict) -> str:
    return json.dumps(metrics, indent=2, ensure_ascii=False)


def _prepare_task(
    samples: list[DatasetSample],
    label_fn,
) -> tuple[list[dict[str, float]], list[int]]:
    rows: list[dict[str, float]] = []
    labels: list[int] = []
    for sample in samples:
        target = label_fn(sample.label)
        if target is None:
            continue
        rows.append(vectorize_sample(sample))
        labels.append(target)
    return rows, labels


def _fit_binary(
    rows: list[dict[str, float]],
    labels: list[int],
    test_size: float,
    random_state: int,
) -> tuple[Pipeline, dict[str, float | None], list[str]]:
    names, matrix = build_matrix(rows)
    pipeline = Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(max_iter=2000, class_weight="balanced"),
            ),
        ]
    )

    metrics: dict[str, float | None]
    if len(set(labels)) < 2:
        pipeline.fit(matrix, labels)
        metrics = {"accuracy": 1.0, "f1": 1.0, "roc_auc": None}
        return pipeline, metrics, names

    X_train, X_test, y_train, y_test = train_test_split(
        matrix,
        labels,
        test_size=test_size,
        random_state=random_state,
        stratify=labels,
    )
    pipeline.fit(X_train, y_train)
    preds = pipeline.predict(X_test)
    probas = pipeline.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probas)) if len(set(y_test)) > 1 else None,
    }
    return pipeline, metrics, names
