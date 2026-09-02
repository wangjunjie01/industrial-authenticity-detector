"""Command-line release gate; exits non-zero when any required threshold fails."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.gates import evaluate_gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regression-tests-passed", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    current = json.loads(args.current.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    result = evaluate_gate(current, candidate, args.regression_tests_passed)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"] and not args.report_only:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
