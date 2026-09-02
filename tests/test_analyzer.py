import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from industrial_authenticity import analyze_text


class AnalyzerTests(unittest.TestCase):
    def test_empty_text_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze_text("   ")

    def test_report_contract(self):
        report = analyze_text(
            "Choose the divider thickness after checking part weight and handling direction. "
            "If operators load from the side, leave enough clearance to avoid edge damage.",
            "linkedin",
        )
        self.assertIn("not an AI-authorship", report["scope_note"])
        self.assertIn("classifier", report)
        self.assertEqual(report["platform"], "linkedin")
        self.assertEqual(len(report["sentences"]), 2)
        self.assertGreater(
            report["industrial_authenticity_engine"]["dimensions"]["decision_density"],
            50,
        )

    def test_formulaic_claims_create_explainable_findings(self):
        report = analyze_text(
            "Firstly, our innovative solution ensures high-quality results. "
            "Moreover, it provides seamless support. Finally, it optimizes everything.",
            "facebook",
        )
        rules = {item["rule"] for item in report["rule_layer"]["findings"]}
        self.assertIn("unsupported_marketing", rules)
        self.assertIn("templated_transition", rules)
        self.assertIn("generic_language", rules)
        self.assertGreater(report["classifier"]["ai_like_writing_risk"], 35)

    def test_chinese_industrial_signals_are_supported(self):
        report = analyze_text(
            "如果零件较重，先核对隔板厚度和装载方向。刚度更高会增加重量，因此需要在保护和周转操作之间取舍。",
            "b2b",
        )
        self.assertEqual(report["statistical_layer"]["sentence_count"], 2)
        self.assertGreater(
            report["industrial_authenticity_engine"]["dimensions"]["engineering_credibility"],
            50,
        )
        self.assertGreater(report["classifier"]["signals"]["decision_markers"], 0)

    def test_unknown_platform_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze_text("A valid sentence.", "reddit")


if __name__ == "__main__":
    unittest.main()
