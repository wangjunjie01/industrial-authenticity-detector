"""Evaluate one transparent detector package on locked calibration/test splits."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import time
import tracemalloc

from benchmarks.metrics import evaluate, threshold_at_fpr
from industrial_authenticity.analyzer import analyze_text
from industrial_authenticity.model import LightweightModel


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(dataset: Path, model_path: Path, output: Path) -> dict:
    rows = _load(dataset)
    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Dataset contains duplicate IDs across locked splits.")
    model_payload = json.loads(model_path.read_text(encoding="utf-8"))
    model = LightweightModel.load(model_path)
    scored = []
    latencies = []
    tracemalloc.start()
    baseline_memory = tracemalloc.get_traced_memory()[1]
    for row in rows:
        start = time.perf_counter()
        report = analyze_text(row["text"], "general", model)
        latencies.append(time.perf_counter() - start)
        scored.append({**row, "score": report["model_detection"]["probability"]})
    peak_memory = max(0, tracemalloc.get_traced_memory()[1] - baseline_memory)
    tracemalloc.stop()
    calibration = [row for row in scored if row["split"] == "calibration"]
    testing = [row for row in scored if row["split"] == "test"]
    if not calibration or not testing:
        raise ValueError("Both calibration and hidden public-test partitions are required.")
    threshold = threshold_at_fpr([row["label"] for row in calibration], [row["score"] for row in calibration])
    labels = [row["label"] for row in testing]
    scores = [row["score"] for row in testing]
    metrics = evaluate(labels, scores, threshold)
    metrics["tpr_at_5_fpr"] = metrics["tpr"]
    human_groups: dict[str, list[dict]] = defaultdict(list)
    for row in testing:
        if row["label"] == 0:
            human_groups[row["genre"]].append(row)
    group_fpr = {
        name: evaluate([row["label"] for row in group], [row["score"] for row in group], threshold)["fpr"]
        for name, group in human_groups.items()
    }
    latency_scale = max(1.0, 2000 / max(1, statistics.mean(len(row["text"]) for row in rows)))
    result = {
        "schema_version": 1,
        "model": {
            "id": model.model_id,
            "version": model.version,
            "source": str(model_path),
            "license": model_payload.get("license"),
            "commercial_use": model_payload.get("commercial_use", False),
            "redistributable": model_payload.get("redistributable", False),
            "release_eligible": model_payload.get("release_eligible", False),
            "source_revision": model_payload.get("source_revision"),
            "training_data_note": model_payload.get("training_data_note", model_payload.get("training_data")),
        },
        "dataset": {
            "source": "liamdugan/raid",
            "revision": "865cac7",
            "samples": len(rows),
            "calibration": len(calibration),
            "test": len(testing),
            "split_policy": "sha256(seed,text): calibration < 51/256; otherwise hidden test",
            "fitting_performed": False,
        },
        "metrics": metrics,
        "human_group_fpr": group_fpr,
        "resources": {
            "package_bytes": model_path.stat().st_size,
            "latency_seconds_2000_chars": statistics.median(latencies) * latency_scale,
            "peak_memory_delta_bytes": peak_memory,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.dataset, args.model, args.output), indent=2))


if __name__ == "__main__":
    main()
