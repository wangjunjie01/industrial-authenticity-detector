"""Acceptance rules for a lightweight detector release candidate."""

from __future__ import annotations


def evaluate_gate(current: dict, candidate: dict, regression_tests_passed: bool = True) -> dict:
    failures: list[str] = []
    candidate_model = candidate.get("model", {})
    if not candidate_model.get("license"):
        failures.append("license_not_declared")
    if candidate_model.get("commercial_use") is not True:
        failures.append("commercial_use_not_permitted")
    if candidate_model.get("redistributable") is not True:
        failures.append("redistribution_not_permitted")
    if candidate_model.get("release_eligible") is not True:
        failures.append("model_not_release_eligible")
    current_metrics = current["metrics"]
    candidate_metrics = candidate["metrics"]
    if candidate_metrics["fpr"] > 0.05:
        failures.append("public_fpr_above_5_percent")
    if candidate_metrics["tpr_at_5_fpr"] < current_metrics["tpr_at_5_fpr"] - 0.02:
        failures.append("tpr_at_5_fpr_regressed_over_2_points")
    if candidate_metrics["balanced_accuracy"] < current_metrics["balanced_accuracy"] - 0.01:
        failures.append("balanced_accuracy_regressed_over_1_point")
    current_groups = current.get("human_group_fpr", {})
    candidate_groups = candidate.get("human_group_fpr", {})
    for group, old_fpr in current_groups.items():
        if group in candidate_groups and candidate_groups[group] > old_fpr + 0.01:
            failures.append(f"human_group_fpr_regressed:{group}")
    if candidate["resources"]["package_bytes"] > 150 * 1024 * 1024:
        failures.append("package_above_150_mb")
    if candidate["resources"]["latency_seconds_2000_chars"] > 1.5:
        failures.append("latency_above_1_5_seconds")
    if candidate["resources"]["peak_memory_delta_bytes"] > 500 * 1024 * 1024:
        failures.append("memory_above_500_mb")
    if not regression_tests_passed:
        failures.append("regression_tests_failed")
    return {"passed": not failures, "failures": failures, "policy_version": "2026-09-02"}
