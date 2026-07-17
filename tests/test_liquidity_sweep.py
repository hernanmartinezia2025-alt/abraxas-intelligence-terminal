from __future__ import annotations

import unittest

from backend.app.analytics.liquidity_sweep import (
    analyze_aggregate_trade_flow,
    build_liquidity_sweep_evaluation,
    detect_sweep,
)


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
        result = build_liquidity_sweep_evaluation(
            candles=candles,
            order_book=order_book,
            aggregate_trades=[],
            microstructure_status=None,
            symbol="BTCUSDT",
            timeframe="1m",
        )
        self.assertFalse(result["order_allowed"])
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["capabilities"]["liquidation_clusters"]["status"], "missing")
        self.assertFalse(result["state_machine"][-1]["reachable"])

    def test_aggregate_trade_flow_requires_impulse_then_reversal(self) -> None:
        trades = []
        for index in range(60):
            trades.append(
                {
                    "aggregate_trade_id": index,
                    "event_time": index,
                    "price": 100 - index * 0.01,
                    "quote_quantity": 100,
                    "aggressor_side": "sell",
                }
            )
        for index in range(60, 85):
            trades.append(
                {
                    "aggregate_trade_id": index,
                    "event_time": index,
                    "price": 99.41 + (index - 59) * 0.02,
                    "quote_quantity": 100,
                    "aggressor_side": "buy",
                }
            )
        result = analyze_aggregate_trade_flow(trades, "bullish_reversal")
        self.assertTrue(result["confirmed"])
        self.assertTrue(result["reversal_aligned"])
        self.assertGreaterEqual(result["impulse_side_share"], 0.55)

    def test_rest_limit_blocks_flow_confirmation(self) -> None:
        trades = [
            {
                "aggregate_trade_id": index,
                "event_time": index,
                "price": 100 - index * 0.0001,
                "quote_quantity": 100,
                "aggressor_side": "sell" if index < 700 else "buy",
            }
            for index in range(1000)
        ]
        result = analyze_aggregate_trade_flow(trades, "bullish_reversal")
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["coverage"], "possibly_truncated_at_1000")


if __name__ == "__main__":
    unittest.main()
