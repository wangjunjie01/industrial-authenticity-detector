"""Fetch a deterministic, stratified public sample from the official RAID dataset."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path

RAID_REVISION = "865cac7"


def _value(row: dict, *names: str, default: str = "unknown") -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return default


def normalize(row: dict, seed: int) -> dict | None:
    text = _value(row, "generation", "text", "content", default="").strip()
    if len(text) < 80:
        return None
    generator = _value(row, "model", "generator").lower()
    label_value = row.get("label")
    if isinstance(label_value, str):
        label = 0 if label_value.lower() in {"human", "0", "false"} else 1
    elif label_value is None:
        label = 0 if generator in {"human", "none"} else 1
    else:
        label = int(bool(label_value))
    attack = _value(row, "attack", default="none")
    genre = _value(row, "domain", "genre")
    digest = hashlib.sha256(f"{seed}\0{text}".encode()).hexdigest()
    return {
        "id": digest[:20],
        "split": "calibration" if int(digest[-2:], 16) < 51 else "test",
        "label": label,
        "genre": genre,
        "generator": generator,
        "attack": attack,
        "text": text,
    }


def fetch(output: Path, count: int, seed: int, scan_limit: int) -> dict:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("Install the benchmark extra: pip install -e '.[benchmark]'") from exc
    stream = load_dataset(
        "liamdugan/raid",
        name="raid",
        split="train",
        streaming=True,
        revision=RAID_REVISION,
    )
    per_stratum = max(2, count // 40)
    buckets: dict[tuple, list[tuple[int, str, dict]]] = {}
    scanned = 0
    for row in stream:
        scanned += 1
        item = normalize(dict(row), seed)
        if item:
            stratum = (item["label"], item["genre"], item["generator"], item["attack"])
            priority = int(hashlib.sha256(f'{seed}:{item["id"]}'.encode()).hexdigest(), 16)
            bucket = buckets.setdefault(stratum, [])
            entry = (-priority, item["id"], item)
            if len(bucket) < per_stratum:
                heapq.heappush(bucket, entry)
            elif entry > bucket[0]:
                heapq.heapreplace(bucket, entry)
        if scanned >= scan_limit:
            break
    selected = [entry[2] for bucket in buckets.values() for entry in bucket]
    selected.sort(key=lambda item: item["id"])
    selected = selected[:count]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in selected), encoding="utf-8")
    return {
        "dataset": "liamdugan/raid",
        "revision": RAID_REVISION,
        "seed": seed,
        "requested": count,
        "selected": len(selected),
        "scanned": scanned,
        "strata": len(buckets),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--scan-limit", type=int, default=200_000)
    args = parser.parse_args()
    print(json.dumps(fetch(args.output, args.count, args.seed, args.scan_limit), indent=2))


if __name__ == "__main__":
    main()
