"""Small, offline classifier for AI-like benchmark pattern detection.

The bundled classifier is deliberately transparent. It estimates similarity to
patterns represented by its calibration configuration; it never identifies an
author and does not transmit text outside the machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_MODEL = files("industrial_authenticity").joinpath("models/bundled-model.json")


@dataclass(frozen=True)
class LightweightModel:
    model_id: str
    version: str
    threshold: float
    intercept: float
    coefficients: dict[str, float]
    applicability: dict[str, Any]
    source_path: str

    @classmethod
    def load(cls, path: str | Path | None = None) -> "LightweightModel":
        source = Path(path) if path else DEFAULT_MODEL
        payload = json.loads(source.read_text(encoding="utf-8"))
        required = {"model_id", "version", "threshold", "intercept", "coefficients", "applicability"}
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"Model configuration is missing: {', '.join(sorted(missing))}")
        coefficients = payload["coefficients"]
        if not isinstance(coefficients, dict) or not coefficients:
            raise ValueError("Model coefficients must be a non-empty object.")
        return cls(
            model_id=str(payload["model_id"]),
            version=str(payload["version"]),
            threshold=float(payload["threshold"]),
            intercept=float(payload["intercept"]),
            coefficients={str(key): float(value) for key, value in coefficients.items()},
            applicability=dict(payload["applicability"]),
            source_path=str(source),
        )

    def _features(self, report: dict) -> dict[str, float]:
        stats = report["statistical_layer"]
        classifier = report["classifier"]
        dimensions = report["industrial_authenticity_engine"]["dimensions"]
        words = max(1, stats["word_count"])
        return {
            "style_risk": classifier["ai_like_writing_risk"] / 100,
            "predictability": stats["predictability_proxy"] / 100,
            "low_burstiness": 1 - stats["burstiness_score"] / 100,
            "finding_density": min(1.0, classifier["signals"]["formulaic_findings"] / max(2, words / 35)),
            "low_decision_density": 1 - dimensions["decision_density"] / 100,
            "low_specificity": 1 - dimensions["specificity"] / 100,
        }

    def predict(self, report: dict) -> dict:
        features = self._features(report)
        score = self.intercept + sum(
            self.coefficients.get(name, 0.0) * value for name, value in features.items()
        )
        probability = 1 / (1 + math.exp(-max(-30.0, min(30.0, score))))
        word_count = report["statistical_layer"]["word_count"]
        min_words = int(self.applicability.get("minimum_words", 40))
        recommended_words = int(self.applicability.get("recommended_words", 100))
        if word_count < min_words:
            confidence = "insufficient"
            applicability = f"Limited: fewer than {min_words} words; treat the probability as unstable."
        elif word_count < recommended_words:
            confidence = "low"
            applicability = f"Partial: {min_words}-{recommended_words - 1} words; manual review is recommended."
        elif abs(probability - self.threshold) < 0.12:
            confidence = "medium"
            applicability = "In scope, but the score is near the calibrated decision threshold."
        else:
            confidence = "high"
            applicability = "In scope for English or Chinese B2B-style prose represented by the declared calibration."
        return {
            "probability": round(probability, 4),
            "probability_percent": round(probability * 100, 1),
            "threshold": self.threshold,
            "classification": "ai_like_pattern" if probability >= self.threshold else "human_like_pattern",
            "confidence": confidence,
            "applicability": applicability,
            "model_id": self.model_id,
            "model_version": self.version,
            "scope_note": (
                "Probability of similarity to calibrated AI-like benchmark patterns; "
                "not the probability that AI authored the text."
            ),
            "offline": True,
        }


def safe_predict(report: dict, model: LightweightModel | None = None) -> dict:
    """Predict with a rule-only fallback if a detector package is unavailable."""
    try:
        return (model or LightweightModel.load()).predict(report)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, json.JSONDecodeError) as exc:
        return {
            "probability": None,
            "probability_percent": None,
            "threshold": None,
            "classification": "unavailable",
            "confidence": "unavailable",
            "applicability": "The lightweight model could not be loaded; writing-style analysis remains available.",
            "model_id": "rule-fallback",
            "model_version": "none",
            "scope_note": "No model probability is reported while the model package is unavailable.",
            "offline": True,
            "error": type(exc).__name__,
        }
