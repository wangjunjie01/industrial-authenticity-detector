"""Dependency-free binary classification metrics used by CI and tests."""

from __future__ import annotations


def confusion(labels: list[int], scores: list[float], threshold: float) -> dict[str, int]:
    result = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for label, score in zip(labels, scores, strict=True):
        predicted = int(score >= threshold)
        result[{(1, 1): "tp", (0, 0): "tn", (0, 1): "fp", (1, 0): "fn"}[(label, predicted)]] += 1
    return result


def rates(labels: list[int], scores: list[float], threshold: float) -> dict[str, float | int]:
    values = confusion(labels, scores, threshold)
    tpr = values["tp"] / max(1, values["tp"] + values["fn"])
    tnr = values["tn"] / max(1, values["tn"] + values["fp"])
    fpr = values["fp"] / max(1, values["fp"] + values["tn"])
    return {**values, "tpr": tpr, "fpr": fpr, "balanced_accuracy": (tpr + tnr) / 2}


def auroc(labels: list[int], scores: list[float]) -> float:
    positives = [score for label, score in zip(labels, scores, strict=True) if label == 1]
    negatives = [score for label, score in zip(labels, scores, strict=True) if label == 0]
    if not positives or not negatives:
        return 0.5
    wins = sum(1 if positive > negative else 0.5 if positive == negative else 0 for positive in positives for negative in negatives)
    return wins / (len(positives) * len(negatives))


def threshold_at_fpr(labels: list[int], scores: list[float], maximum_fpr: float = 0.05) -> float:
    candidates = sorted({0.0, 1.0, *scores}, reverse=True)
    eligible = [threshold for threshold in candidates if rates(labels, scores, threshold)["fpr"] <= maximum_fpr]
    if not eligible:
        return 1.0
    return min(eligible, key=lambda threshold: (-float(rates(labels, scores, threshold)["tpr"]), threshold))


def evaluate(labels: list[int], scores: list[float], threshold: float) -> dict[str, float | int]:
    return {"auroc": auroc(labels, scores), **rates(labels, scores, threshold), "threshold": threshold}
