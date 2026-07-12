import unittest

from backend.app.services.macro_market_service import _correlation_reading, _pearson


class MacroCorrelationTests(unittest.TestCase):
    def test_pearson_uses_direction_of_returns(self) -> None:
        left = [0.01, -0.02, 0.03, -0.01, 0.04]
        self.assertAlmostEqual(_pearson(left, left), 1.0)
        self.assertAlmostEqual(_pearson(left, [-value for value in left]), -1.0)

    def test_reading_selects_strongest_btc_relationship(self) -> None:
        reading = _correlation_reading([
            {"left": "BTC", "right": "SPX", "correlation": 0.48, "samples": 60, "status": "ready"},
            {"left": "BTC", "right": "WTI", "correlation": -0.18, "samples": 57, "status": "ready"},
            {"left": "SPX", "right": "NASDAQ", "correlation": 0.96, "samples": 89, "status": "ready"},
        ])
        self.assertEqual(reading["dominant_pair"], "BTC / SPX")
        self.assertEqual(reading["strength"], "moderate")
        self.assertIn("no una señal", reading["caveat"])

    def test_reading_reports_insufficient_btc_data(self) -> None:
        reading = _correlation_reading([
            {"left": "BTC", "right": "SPX", "correlation": None, "samples": 10, "status": "insufficient_data"}
        ])
        self.assertEqual(reading["status"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
