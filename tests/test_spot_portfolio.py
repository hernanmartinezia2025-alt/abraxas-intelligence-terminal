from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.app.storage import sqlite as storage_sqlite
from backend.app.analytics.spot_analysis import analyze_spot_candles
from backend.app.storage.sqlite import connect, initialize_database
from backend.app.storage.spot_portfolio import execute_spot_transaction, portfolio_snapshot, project_contributions


class SpotPortfolioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = storage_sqlite.DB_PATH
        storage_sqlite.DB_PATH = Path(self.temp_dir.name) / "spot.db"
        initialize_database()
        with connect() as connection:
            connection.execute(
                """INSERT INTO market_snapshots (timestamp, symbol, price, change_24h, volume_24h,
                fear_greed_value, fear_greed_label, risk_level, abraxas_reading)
                VALUES (?, 'BTCUSDT', 50000, 0, 1000000, 50, 'Neutral', 'NORMAL', 'fixture')""",
                (datetime.now(timezone.utc).isoformat(),),
            )

    def tearDown(self) -> None:
        storage_sqlite.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_buy_updates_cash_holding_and_audit_transaction(self) -> None:
        result = execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1, "notes": "long term"})
        snapshot = result["snapshot"]
        self.assertEqual(len(snapshot["holdings"]), 1)
        self.assertAlmostEqual(snapshot["holdings"][0]["quantity"], 0.1)
        self.assertAlmostEqual(snapshot["portfolio"]["cash_balance"], 4995.0)
        self.assertEqual(snapshot["transactions"][0]["source"], "market_snapshots")

    def test_projection_is_explicit_user_assumption(self) -> None:
        projection = project_contributions(1000, 100, 2, 0)
        self.assertEqual(projection["final_value"], 3400)
        self.assertEqual(projection["mode"], "user_assumption_scenario")

    def test_daily_analysis_exposes_evidence_without_asserting_elliott_count(self) -> None:
        candles = [
            {"timestamp": index, "open": 100 + index, "high": 102 + index, "low": 98 + index, "close": 101 + index, "volume": 1000 + index}
            for index in range(220)
        ]
        analysis = analyze_spot_candles("BTCUSDT", "1d", candles)
        self.assertEqual(analysis["chartism"]["trend"], "strong_uptrend")
        self.assertEqual(analysis["elliott"]["status"], "manual_count_required")
        self.assertEqual(analysis["wyckoff"]["status"], "heuristic_hypothesis")
        strategy = analysis["trading_latino_5f"]
        self.assertEqual(strategy["contract"], "trading_latino_5f_v1")
        self.assertEqual(strategy["mode"], "spot_long_only_observation")
        self.assertEqual(strategy["filters_total"], 5)
        self.assertEqual(set(strategy["filters"]), {"directionality", "adx_strength", "ema_value_area", "volume_profile", "time"})
        self.assertIn(strategy["decision"], {"blocked", "buy_candidate"})
        self.assertEqual(strategy["filters"]["adx_strength"]["method"], "wilder_adx_14")
        self.assertIn("Approximate POC", strategy["filters"]["volume_profile"]["warning"])
        self.assertIn("never places an order", strategy["guardrail"])


if __name__ == "__main__":
    unittest.main()
