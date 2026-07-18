from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.app.storage import sqlite as storage_sqlite
from backend.app.analytics.spot_analysis import analyze_spot_candles
from backend.app.services.data_center_service import get_dataset_preview
from backend.app.strategies.market_modes import build_market_mode_policy
from backend.app.storage.sqlite import connect, initialize_database
from backend.app.storage.spot_portfolio import (
    SpotRiskRejected,
    apply_cash_flow,
    execute_spot_transaction,
    portfolio_snapshot,
    project_contributions,
    quote_spot_transaction,
    record_portfolio_valuation,
    reset_spot_portfolio,
)
from backend.app.storage.risk import set_kill_switch, update_risk_limits


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
        update_risk_limits({
            "max_position_pct": 100, "max_daily_loss_pct": 100, "max_drawdown_pct": 100,
            "cooldown_minutes": 0, "symbol_whitelist": ["BTCUSDT"],
        })
        set_kill_switch(False, "Spot portfolio test")

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
        self.assertIsNotNone(snapshot["transactions"][0]["risk_validation_id"])
        self.assertEqual(snapshot["ledger"][0]["event_type"], "spot_transaction")
        self.assertEqual(len(snapshot["equity_history"]), 1)

    def test_quote_is_read_only_and_exposes_full_cost(self) -> None:
        quote = quote_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1})
        self.assertTrue(quote["allowed"])
        self.assertFalse(quote["execution_created"])
        self.assertTrue(quote["risk_allowed"])
        self.assertIsNone(quote["risk"]["validation_id"])
        self.assertAlmostEqual(quote["notional"], 5000.0)
        self.assertAlmostEqual(quote["fee"], 5.0)
        self.assertEqual(portfolio_snapshot()["transactions"], [])
        with connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM risk_validation_log").fetchone()[0], 0)

    def test_kill_switch_blocks_manual_buy_but_allows_reducing_sell(self) -> None:
        bought = execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1})
        self.assertIsNotNone(bought["transaction"]["risk_validation_id"])
        set_kill_switch(True, "Manual spot emergency fixture")
        blocked_quote = quote_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01})
        self.assertFalse(blocked_quote["allowed"])
        with self.assertRaises(SpotRiskRejected):
            execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01})
        sold = execute_spot_transaction({"symbol": "BTCUSDT", "side": "sell", "quantity": 0.05})
        self.assertEqual(sold["transaction"]["side"], "sell")
        self.assertIsNotNone(sold["transaction"]["risk_validation_id"])

    def test_risk_validation_cannot_authorize_a_different_transaction(self) -> None:
        first = execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01})
        validation_id = first["transaction"]["risk_validation_id"]
        with self.assertRaisesRegex(ValueError, "does not authorize"):
            execute_spot_transaction({
                "symbol": "BTCUSDT",
                "side": "buy",
                "quantity": 0.02,
                "origin": "rebalance_run",
                "origin_reference": "test:mismatched-risk",
                "risk_validation_id": validation_id,
            })
        self.assertEqual(len(portfolio_snapshot()["transactions"]), 1)

    def test_cash_flow_is_not_counted_as_market_profit(self) -> None:
        result = apply_cash_flow({"flow_type": "deposit", "amount": 500, "notes": "monthly DCA"})
        snapshot = result["snapshot"]
        self.assertAlmostEqual(snapshot["equity"], 10_500.0)
        self.assertAlmostEqual(snapshot["net_contributions"], 10_500.0)
        self.assertAlmostEqual(snapshot["total_pnl"], 0.0)
        self.assertEqual(snapshot["cash_flows"][0]["flow_type"], "deposit")
        self.assertEqual(len(get_dataset_preview("spot_cash_flows", limit=10)["rows"]), 1)
        self.assertEqual(len(get_dataset_preview("spot_portfolio_ledger", limit=10)["rows"]), 1)
        self.assertEqual(len(get_dataset_preview("spot_equity_snapshots", limit=10)["rows"]), 1)

    def test_valuation_is_idempotent_until_market_mark_changes(self) -> None:
        execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1})
        duplicate = record_portfolio_valuation()
        self.assertFalse(duplicate["recorded"])
        with connect() as connection:
            connection.execute(
                """INSERT INTO market_snapshots (timestamp, symbol, price, change_24h, volume_24h,
                fear_greed_value, fear_greed_label, risk_level, abraxas_reading)
                VALUES (?, 'BTCUSDT', 51000, 0, 1000000, 50, 'Neutral', 'NORMAL', 'fixture 2')""",
                (datetime.now(timezone.utc).isoformat(),),
            )
        changed = record_portfolio_valuation()
        self.assertTrue(changed["recorded"])
        self.assertEqual(len(changed["snapshot"]["equity_history"]), 2)

    def test_reset_starts_new_cycle_without_deleting_audit_history(self) -> None:
        execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1})
        reset = reset_spot_portfolio(20_000, "new allocation mandate")
        snapshot = reset["snapshot"]
        self.assertEqual(reset["cycle_number"], 2)
        self.assertEqual(snapshot["portfolio"]["active_cycle"], 2)
        self.assertEqual(snapshot["holdings"], [])
        self.assertEqual(snapshot["transactions"], [])
        self.assertAlmostEqual(snapshot["equity"], 20_000.0)
        self.assertEqual(snapshot["ledger"][0]["event_type"], "portfolio_reset")
        self.assertTrue(any(row["event_type"] == "spot_transaction" for row in snapshot["ledger"]))

    def test_projection_is_explicit_user_assumption(self) -> None:
        projection = project_contributions(1000, 100, 2, 0)
        self.assertEqual(projection["final_value"], 3400)
        self.assertEqual(projection["mode"], "user_assumption_scenario")

    def test_spot_and_futures_are_hard_separated(self) -> None:
        policy = build_market_mode_policy(
            "1d",
            {
                "limits": {"max_position_pct": 10, "max_daily_loss_pct": 3, "max_drawdown_pct": 12},
                "kill_switch": {"active": True},
            },
        )
        self.assertEqual(policy["contract"], "market_mode_separation_v1")
        self.assertTrue(policy["spot"]["timeframe_allowed"])
        self.assertEqual(policy["spot"]["leverage"], 1)
        self.assertEqual(policy["futures"]["status"], "locked")
        self.assertFalse(policy["futures"]["execution_supported"])
        self.assertEqual(policy["futures"]["stop_loss"], "mandatory")
        self.assertEqual(policy["futures"]["leverage"]["hard_max"], 10)
        self.assertEqual(policy["mode_conversion"], "forbidden")

    def test_daily_analysis_exposes_evidence_without_asserting_elliott_count(self) -> None:
        candles = [
            {"timestamp": index, "open": 100 + index, "high": 102 + index, "low": 98 + index, "close": 101 + index, "volume": 1000 + index}
            for index in range(220)
        ]
        analysis = analyze_spot_candles(
            "BTCUSDT",
            "1d",
            candles,
            sentiment={"value": 20, "regime": "FUD_EXTREME", "source": "test fixture"},
            risk_profile={
                "limits": {"max_position_pct": 10, "max_daily_loss_pct": 3, "max_drawdown_pct": 12},
                "kill_switch": {"active": True, "reason": "test lock"},
            },
        )
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
        doctrine = analysis["trading_latino_doctrine"]
        self.assertEqual(doctrine["contract"], "trading_latino_doctrine_v1")
        self.assertFalse(doctrine["order_allowed"])
        self.assertEqual(doctrine["principles"]["liquidity_footprint"]["status"], "observable_proxy")
        self.assertEqual(doctrine["principles"]["probability_discipline"]["status"], "edge_unverified")
        self.assertEqual(doctrine["principles"]["probability_discipline"]["sample_size"], 0)
        self.assertEqual(doctrine["principles"]["contrarian_psychology"]["status"], "watch_accumulation_after_confirmation")
        self.assertTrue(doctrine["principles"]["capital_survival"]["kill_switch_active"])
        self.assertEqual(analysis["market_mode_policy"]["active_mode"], "spot_portfolio_simulation")
        self.assertEqual(analysis["market_mode_policy"]["futures"]["status"], "locked")


if __name__ == "__main__":
    unittest.main()
