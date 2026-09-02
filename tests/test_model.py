import json
from pathlib import Path
import tempfile
import unittest

from industrial_authenticity import analyze_text
from industrial_authenticity.model import LightweightModel, safe_predict


class ModelTests(unittest.TestCase):
    def test_dual_track_contract_and_short_text_confidence(self):
        report = analyze_text("Choose 5 mm dividers after checking the part load.")
        self.assertIn("writing_style_risk", report)
        self.assertIn("model_detection", report)
        self.assertEqual(report["model_detection"]["confidence"], "insufficient")
        self.assertIn("not the probability that AI authored", report["model_detection"]["scope_note"])
        self.assertEqual(report["model_detection"]["model_version"], report["detector_bundle_version"])

    def test_invalid_model_falls_back_without_breaking_style_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text(json.dumps({"model_id": "broken"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                LightweightModel.load(path)
        fallback = safe_predict({}, model=object())
        self.assertEqual(fallback["classification"], "unavailable")
        self.assertIsNone(fallback["probability"])


if __name__ == "__main__":
    unittest.main()
