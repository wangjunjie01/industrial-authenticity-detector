import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from industrial_authenticity.optimizer import OPTIMIZER_VERSION, optimize_text


class OptimizerTests(unittest.TestCase):
    def test_formulaic_english_copy_improves_without_targeting_model_probability(self):
        source = (
            "Firstly, our innovative solution ensures high-quality results. "
            "It is important to note that it offers unmatched results. "
            "In conclusion, it provides seamless support. Finally, it optimizes everything."
        )
        result = optimize_text(source, "linkedin")

        self.assertEqual(result["optimizer_version"], OPTIMIZER_VERSION)
        self.assertEqual(result["status"], "improved")
        self.assertTrue(result["safety"]["passed"])
        self.assertGreater(
            result["optimized_analysis"]["industrial_authenticity_engine"]["score"],
            result["original_analysis"]["industrial_authenticity_engine"]["score"],
        )
        self.assertFalse(result["score_changes"]["model_detection"]["used_for_selection"])
        optimized = result["optimized_text"].lower()
        for phrase in ("firstly", "it is important to note", "in conclusion", "unmatched"):
            self.assertNotIn(phrase, optimized)

    def test_confirmed_facts_are_used_and_unconfirmed_facts_are_not(self):
        source = "Choose the divider after checking the load direction."
        facts = {
            "specifications_constraints": "Use 5 mm PP sheet at 12 kg static load.",
            "failure_risk_check": "Reject the part if the edge cracks during inspection.",
        }
        confirmed = optimize_text(source, "b2b", facts, True)
        unconfirmed = optimize_text(source, "b2b", facts, False)

        self.assertIn("5 mm", confirmed["optimized_text"])
        self.assertIn("12 kg", confirmed["optimized_text"])
        self.assertNotIn("5 mm", unconfirmed["optimized_text"])
        self.assertEqual(len(unconfirmed["fact_ledger"]["unconfirmed"]), 2)

    def test_numbers_units_conditions_and_negation_are_preserved(self):
        source = (
            "Do not approve the 600 x 400 x 300 mm tray unless the 12 kg load "
            "passes the edge check."
        )
        result = optimize_text(
            source,
            "b2b",
            {"tradeoff_preference": "Recommend approval only after the edge check passes."},
            True,
        )

        candidate = result["optimized_text"]
        for item in ("not", "600", "400", "300 mm", "12 kg", "unless"):
            self.assertIn(item, candidate)
        self.assertTrue(result["safety"]["passed"])

    def test_unverified_claims_are_not_invented_for_chinese_or_mixed_copy(self):
        source = "这款 PP 隔板用于周转箱。If the load changes, check the stacking direction."
        result = optimize_text(source, "b2b")

        for claim in ("认证", "客户实现", "节省金额", "ROI", "certified"):
            self.assertNotIn(claim, result["optimized_text"])
        self.assertTrue(result["safety"]["passed"])

    def test_missing_facts_are_reported_bilingually(self):
        result = optimize_text("This product provides support.", "general")

        self.assertIn(result["status"], {"improved", "blocked_by_missing_facts"})
        self.assertTrue(result["unresolved_fact_requests"])
        for request in result["unresolved_fact_requests"]:
            self.assertTrue(request["message_zh"])
            self.assertTrue(request["message_en"])

    def test_supported_channels_preserve_source_language_and_facts(self):
        source = "Check the load. Select the divider. Record the result. Release the tray."
        for platform in ("linkedin", "facebook", "blog", "b2b", "general"):
            with self.subTest(platform=platform):
                result = optimize_text(source, platform)
                self.assertEqual(result["platform"], platform)
                self.assertIn("load", result["optimized_text"].lower())
                self.assertNotRegex(result["optimized_text"], r"[\u4e00-\u9fff]")
                self.assertTrue(result["safety"]["passed"])

    def test_rejects_empty_overlong_and_unknown_fact_input(self):
        with self.assertRaises(ValueError):
            optimize_text(" ")
        with self.assertRaises(ValueError):
            optimize_text("x" * 50_001)
        with self.assertRaises(ValueError):
            optimize_text("Valid text.", verified_facts={"remote_url": "https://example.com"})


if __name__ == "__main__":
    unittest.main()
