from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from app.config import get_ml_model_path
from app.ml.features import vectorize_row
from app.ml.prediction import MlPrediction


class MlAdvisor:
    """Carga modelos entrenados y expone probabilidades (no modera)."""

    def __init__(self, model_path: Path | None = None) -> None:
        self._path = model_path or get_ml_model_path()
        self._bundle: dict | None = None
        self._load()

    @property
    def enabled(self) -> bool:
        return self._bundle is not None

    @property
    def model_path(self) -> Path:
        return self._path

    def predict(
        self,
        *,
        message_features: dict,
        user_features: dict,
        spam_score: int,
        automation_score: int,
        detection_signals: dict | None = None,
    ) -> MlPrediction | None:
        if not self._bundle:
            return None
        row = vectorize_row(
            message_features=message_features,
            user_features=user_features,
            spam_score=spam_score,
            automation_score=automation_score,
            detection_signals=detection_signals,
        )
        spam_prob = self._predict_one(
            self._bundle["spam_pipeline"],
            row,
            self._bundle.get("spam_feature_names") or [],
        )
        auto_prob = self._predict_one(
            self._bundle["automation_pipeline"],
            row,
            self._bundle.get("automation_feature_names") or [],
        )
        if spam_prob is None or auto_prob is None:
            return None
        return MlPrediction(
            spam_probability=spam_prob,
            automation_probability=auto_prob,
        )

    def _predict_one(
        self,
        pipeline: Pipeline,
        row: dict[str, float],
        names: list[str],
    ) -> float | None:
        if not names:
            return None
        vector = [row.get(name, 0.0) for name in names]
        proba = pipeline.predict_proba([vector])[0]
        if len(proba) < 2:
            return float(proba[0])
        return float(proba[1])

    def _load(self) -> None:
        if not self._path.is_file():
            self._bundle = None
            return
        try:
            bundle = joblib.load(self._path)
        except Exception:
            self._bundle = None
            return
        if not isinstance(bundle, dict):
            self._bundle = None
            return
        if "spam_pipeline" not in bundle or "automation_pipeline" not in bundle:
            self._bundle = None
            return
        self._bundle = bundle
