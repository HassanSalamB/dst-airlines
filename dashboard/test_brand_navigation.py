from pathlib import Path
import unittest


APP_SOURCE = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")


class BrandNavigationTest(unittest.TestCase):
    def test_portfolio_home_link_uses_hsb_brand_icon(self):
        self.assertIn("https://hassansalamb.dev/favicon.svg?v=2", APP_SOURCE)
        self.assertNotIn('html.A("⌂"', APP_SOURCE)
        self.assertIn('aria-label":"Back to hassansalamb.dev"', APP_SOURCE)

    def test_sidebar_uses_consolidated_product_sections(self):
        for label in [
            "Live Airspace",
            "Historical Overview",
            "Performance Explorer",
            "Risk Analyzer",
            "AI Delay Lab",
        ]:
            self.assertIn(label, APP_SOURCE)

        for old_page in ["Airlines", "Airports", "Routes", "Trends", "Prediction Lab"]:
            self.assertNotIn(f',"{old_page}",', APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
