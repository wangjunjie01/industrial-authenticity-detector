"""Create a deterministic lightweight detector archive and signed-manifest input."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

REPOSITORY = "wangjunjie01/industrial-authenticity-detector"


def build(model_path: Path, report_path: Path, output_dir: Path, version: str) -> tuple[Path, Path]:
    model = json.loads(model_path.read_text(encoding="utf-8"))
    model["version"] = version
    report = json.loads(report_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"detector-bundle-{version}.zip"
    model_bytes = (json.dumps(model, ensure_ascii=False, indent=2) + "\n").encode()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        info = zipfile.ZipInfo("model.json", date_time=(2026, 1, 1, 0, 0, 0))
        info.external_attr = 0o644 << 16
        bundle.writestr(info, model_bytes)
    manifest = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "version": version,
        "minimum_app_version": "0.2.0",
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "size": archive.stat().st_size,
        "model_id": model["model_id"],
        "evaluation": report.get("metrics", {}),
        "rollback": "The previous active detector remains available through the local rollback control.",
    }
    manifest_path = output_dir / "detector-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return archive, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    archive, manifest = build(args.model, args.report, args.output_dir, args.version)
    print(archive)
    print(manifest)


if __name__ == "__main__":
    main()
