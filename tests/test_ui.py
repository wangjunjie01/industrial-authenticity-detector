from importlib.resources import files
import unittest


class UiTests(unittest.TestCase):
    def test_dual_results_and_update_controls_are_present(self):
        html = files("industrial_authenticity").joinpath("web/index.html").read_text(encoding="utf-8")
        for required in ("risk", "model-probability", "update-button", "rollback-button", "corpus-import"):
            self.assertIn(required, html)


if __name__ == "__main__":
    unittest.main()
