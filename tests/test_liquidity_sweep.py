from __future__ import annotations

import unittest

from backend.app.analytics.liquidity_sweep import build_liquidity_sweep_evaluation, detect_sweep


def candles_with_last(last: dict) -> list[dict]:
    candles = []
    for index in range(70):
        base = 100 + (index % 5) * 0.05
        candles.append(
            {
                "timestamp": index * 60_000,
                "close_time": index * 60_000 + 59_999,
                "open": base,
                "high": base + 0.6,
                "low": base - 0.6,
                "close": base + 0.1,
                "volume": 100 + index % 7,
            }
        )
    candles.append({"timestamp": 70 * 60_000, "close_time": 70 * 60_000 + 59_999, **last})
    return candles


class LiquiditySweepTests(unittest.TestCase):
    def test_bullish_reclaim_requires_wick_and_volume(self) -> None:
        candles = candles_with_last(
            {"open": 99.8, "high": 100.5, "low": 97.0, "close": 100.2, "volume": 1000}
        )
        result = detect_sweep(candles)
        self.assertEqual(result["direction"], "bullish_reversal")
        self.assertTrue(result["qualified"])
        self.assertTrue(result["checks"]["reclaimed_prior_extreme"])
        self.assertGreaterEqual(result["wick_share"], result["wick_threshold"])
        self.assertGreaterEqual(result["volume_z_score"], result["volume_z_threshold"])

    def test_break_without_reclaim_is_not_a_sweep(self) -> None:
        candles = candles_with_last(
            {"open": 99.8, "high": 100.0, "low": 97.0, "close": 97.5, "volume": 1000}
        )
        result = detect_sweep(candles)
        self.assertEqual(result["direction"], "none")
        self.assertFalse(result["qualified"])

    def test_evaluation_is_always_non_executing(self) -> None:
        candles = candles_with_last(
            {"open": 99.8, "high": 100.5, "low": 97.0, "close": 100.2, "volume": 1000}
        )
        order_book = {
            "source": "test",
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "best_bid": 100.1,
            "best_ask": 100.2,
            "spread_percent": 0.1,
            "asks": [
                {"price": 100.3, "quantity": 1, "notional": 100.3},
                {"price": 102.0, "quantity": 10, "notional": 1020.0},
                {"price": 103.0, "quantity": 1, "notional": 103.0},
            ],
            "bids": [],
        }
        result = build_liquidity_sweep_evaluation(candles, order_book, "BTCUSDT", "1m")
        self.assertFalse(result["order_allowed"])
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["capabilities"]["liquidation_clusters"]["status"], "missing")
        self.assertFalse(result["state_machine"][-1]["reachable"])


if __name__ == "__main__":
    unittest.main()
