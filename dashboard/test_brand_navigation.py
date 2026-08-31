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

    def test_performance_explorer_owns_route_and_flight_drilldown(self):
        for identifier in [
            "performance-date-from",
            "performance-date-to",
            "performance-date-summary",
            "performance-section",
            "perf-tab-carrier",
            "perf-tab-network",
            "perf-tab-flights",
            "chart-airport-map",
            "chart-heatmap",
            "chart-bubble",
            "flight-lookup-table",
        ]:
            self.assertIn(identifier, APP_SOURCE)

        for removed_route_graph_identifier in [
            "Airport Route Graph",
            "page_graph",
            "graph-from",
            "graph-to",
            "btn-graph",
            "graph-result",
            "lookup-flight-date",
            "gulf-focus",
        ]:
            self.assertNotIn(removed_route_graph_identifier, APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
