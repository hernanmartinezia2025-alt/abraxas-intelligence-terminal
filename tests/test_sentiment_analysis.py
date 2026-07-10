import unittest

from backend.app.market.sentiment_analysis import build_sentiment_analysis


def row(symbol: str, value: int, change: float, timestamp: str = "2026-07-10T12:00:00+00:00") -> dict:
    return {
        "symbol": symbol,
        "fear_greed_value": value,
        "fear_greed_label": "Extreme Fear" if value <= 24 else "Neutral",
        "change_24h": change,
        "timestamp": timestamp,
    }


class SentimentAnalysisTests(unittest.TestCase):
    def test_extreme_fear_is_a_watch_not_an_order(self) -> None:
        result = build_sentiment_analysis([row("BTCUSDT", 23, -2), row("ETHUSDT", 23, 1)])
        self.assertEqual(result["regime"], "FUD_EXTREME")
        self.assertEqual(result["market_breadth"]["positive"], 1)
        self.assertEqual(result["market_breadth"]["negative"], 1)
        self.assertIn("no perseguir", result["guidance"].lower())

    def test_fomo_extreme_reports_breadth_from_latest_snapshot(self) -> None:
        result = build_sentiment_analysis([
            row("BTCUSDT", 80, 4, "2026-07-10T12:01:00+00:00"),
            row("BTCUSDT", 80, 1, "2026-07-10T12:00:00+00:00"),
            row("ETHUSDT", 80, -1, "2026-07-10T12:01:00+00:00"),
        ])
        self.assertEqual(result["regime"], "FOMO_EXTREME")
        self.assertEqual(result["market_breadth"]["tracked_assets"], 2)
        self.assertEqual(result["market_breadth"]["positive"], 1)
        self.assertEqual(result["market_breadth"]["negative"], 1)

