import unittest

from benchmarks.gates import evaluate_gate
from benchmarks.metrics import auroc, evaluate, threshold_at_fpr


def report(fpr=0.04, tpr=0.8, balanced=0.85, size=1000, latency=0.1, memory=1000, groups=None):
    return {
        "model": {"license": "MIT", "commercial_use": True, "redistributable": True, "release_eligible": True},
        "metrics": {"fpr": fpr, "tpr_at_5_fpr": tpr, "balanced_accuracy": balanced},
        "human_group_fpr": groups or {"news": 0.03},
        "resources": {"package_bytes": size, "latency_seconds_2000_chars": latency, "peak_memory_delta_bytes": memory},
    }


class BenchmarkTests(unittest.TestCase):
    def test_metrics_are_correct_and_threshold_is_calibrated(self):
        labels = [0, 0, 0, 1, 1, 1]
        scores = [0.1, 0.2, 0.3, 0.65, 0.8, 0.9]
        threshold = threshold_at_fpr(labels, scores, 0.05)
        metrics = evaluate(labels, scores, threshold)
        self.assertEqual(metrics["fpr"], 0)
        self.assertEqual(metrics["tpr"], 1)
        self.assertEqual(auroc(labels, scores), 1)

    def test_gate_accepts_equal_candidate(self):
        self.assertTrue(evaluate_gate(report(), report(), True)["passed"])

    def test_gate_blocks_each_resource_or_accuracy_regression(self):
        result = evaluate_gate(
            report(),
            report(fpr=0.06, tpr=0.75, balanced=0.82, size=151 * 1024 * 1024, latency=1.6, memory=501 * 1024 * 1024, groups={"news": 0.05}),
            False,
        )
        self.assertFalse(result["passed"])
        self.assertGreaterEqual(len(result["failures"]), 8)

    def test_gate_blocks_uncleared_license_and_redistribution(self):
        candidate = report()
        candidate["model"] = {}
        result = evaluate_gate(report(), candidate, True)
        self.assertFalse(result["passed"])
        self.assertIn("license_not_declared", result["failures"])
        self.assertIn("commercial_use_not_permitted", result["failures"])
        self.assertIn("redistribution_not_permitted", result["failures"])


if __name__ == "__main__":
    unittest.main()
