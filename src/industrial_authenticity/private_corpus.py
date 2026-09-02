"""Local-only, privacy-preserving industrial acceptance corpus."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

from .analyzer import analyze_text
from .model import LightweightModel


ALLOWED_CATEGORIES = {"linkedin", "facebook", "blog", "product", "b2b"}


@dataclass
class PrivateCorpus:
    root: Path

    def __post_init__(self) -> None:
        self.path = self.root / "private_corpus" / "samples.jsonl"

    def import_samples(self, samples: Iterable[dict]) -> dict:
        cleaned = []
        for item in samples:
            text = str(item.get("text", "")).strip()
            category = str(item.get("category", "b2b")).lower().strip()
            if not text:
                continue
            if category not in ALLOWED_CATEGORIES:
                raise ValueError(f"Unsupported private-corpus category: {category}")
            if len(text) > 50_000:
                raise ValueError("A private-corpus sample exceeds 50,000 characters.")
            sample_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            cleaned.append({"id": sample_id, "category": category, "text": text})
        if not cleaned:
            raise ValueError("Provide at least one non-empty private-corpus sample.")
        if len(cleaned) > 500:
            raise ValueError("At most 500 samples can be imported at one time.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = {sample["id"]: sample for sample in self._load()}
        existing.update({sample["id"]: sample for sample in cleaned})
        with self.path.open("w", encoding="utf-8") as handle:
            for sample in existing.values():
                handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
        return self.status()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        samples = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                samples.append(json.loads(line))
        return samples

    def status(self) -> dict:
        samples = self._load()
        categories: dict[str, int] = {}
        for sample in samples:
            categories[sample["category"]] = categories.get(sample["category"], 0) + 1
        return {
            "sample_count": len(samples),
            "categories": categories,
            "sufficient": len(samples) >= 20,
            "message": (
                "Local industry validation is ready."
                if len(samples) >= 20
                else "Industry local validation samples are insufficient; 20 or more are recommended."
            ),
            "privacy": "Only aggregate metrics and anonymous sample IDs leave analysis memory; raw text stays local.",
        }

    def validate(self, current: LightweightModel, candidate: LightweightModel) -> dict:
        samples = self._load()
        if not samples:
            return {
                **self.status(),
                "allowed": True,
                "current_false_positive_rate": None,
                "candidate_false_positive_rate": None,
                "blocking_regressions": 0,
            }
        current_positive = 0
        candidate_positive = 0
        blocking = 0
        anonymous_failures = []
        for sample in samples:
            platform = sample["category"] if sample["category"] in {"linkedin", "facebook", "blog", "b2b"} else "b2b"
            try:
                old_report = analyze_text(sample["text"], platform, current)
                new_report = analyze_text(sample["text"], platform, candidate)
                current_positive += old_report["model_detection"]["classification"] == "ai_like_pattern"
                candidate_positive += new_report["model_detection"]["classification"] == "ai_like_pattern"
                if len(old_report["sentences"]) != len(new_report["sentences"]) or not new_report["revision_plan"]:
                    blocking += 1
                    anonymous_failures.append(sample["id"])
            except Exception:  # candidate acceptance must fail closed per sample
                blocking += 1
                anonymous_failures.append(sample["id"])
        total = len(samples)
        current_fpr = current_positive / total
        candidate_fpr = candidate_positive / total
        allowed = blocking == 0 and (candidate_fpr <= 0.05 or candidate_fpr <= current_fpr + 0.01)
        return {
            **self.status(),
            "allowed": allowed,
            "current_false_positive_rate": round(current_fpr, 4),
            "candidate_false_positive_rate": round(candidate_fpr, 4),
            "blocking_regressions": blocking,
            "anonymous_failure_ids": anonymous_failures,
        }

