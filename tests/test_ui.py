from importlib.resources import files
import unittest


class UiTests(unittest.TestCase):
    def test_dual_results_and_update_controls_are_present(self):
        html = files("industrial_authenticity").joinpath("web/index.html").read_text(encoding="utf-8")
        for required in ("risk", "model-probability", "model-classification", "update-button", "rollback-button", "corpus-import"):
            self.assertIn(required, html)

    def test_page_displays_chinese_and_english_together(self):
        web = files("industrial_authenticity").joinpath("web")
        html = web.joinpath("index.html").read_text(encoding="utf-8")
        javascript = web.joinpath("app.js").read_text(encoding="utf-8")
        self.assertIn('<html lang="zh-CN">', html)
        for chinese, english in (
            ("工业真实性检测器", "Industrial Authenticity Detector"),
            ("写作风格风险", "Writing style risk"),
            ("确认升级", "Confirm upgrade"),
            ("本地行业验证样本", "Local industry validation samples"),
        ):
            self.assertIn(chinese, html)
            self.assertIn(english, html)
        for chinese, english in (
            ("分析文案", "Analyze draft"),
            ("样本不足", "Insufficient"),
            ("工程可信度", "Engineering credibility"),
            ("已是最新版本", "Up to date"),
            ("更像人工写作模式", "more human-like pattern"),
            ("结论置信度", "Conclusion confidence"),
        ):
            self.assertIn(chinese, javascript)
            self.assertIn(english, javascript)


if __name__ == "__main__":
    unittest.main()
