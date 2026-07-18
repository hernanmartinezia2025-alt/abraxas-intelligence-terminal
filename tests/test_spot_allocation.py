from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.data_center_service import get_dataset_preview
from backend.app.storage import sqlite as storage_sqlite
from backend.app.storage.spot_allocation import (
    apply_rebalance_run,
    archive_allocation_policy,
    create_rebalance_run,
    list_allocation_policies,
    save_allocation_policy,
)
from backend.app.storage.spot_portfolio import execute_spot_transaction, portfolio_snapshot
from backend.app.storage.risk import set_kill_switch, update_risk_limits, validate_order_intent
from backend.app.storage.sqlite import connect, initialize_database


class SpotAllocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = storage_sqlite.DB_PATH
        storage_sqlite.DB_PATH = Path(self.temp_dir.name) / "spot-allocation.db"
        initialize_database()
        now = datetime.now(timezone.utc).isoformat()
        with connect() as connection:
            for symbol, price in (("BTCUSDT", 50_000), ("ETHUSDT", 2_500)):
                connection.execute(
                    """INSERT INTO market_snapshots (timestamp, symbol, price, change_24h, volume_24h,
                    fear_greed_value, fear_greed_label, risk_level, abraxas_reading)
                    VALUES (?, ?, ?, 0, 1000000, 50, 'Neutral', 'NORMAL', 'fixture')""",
                    (now, symbol, price),
                )
        update_risk_limits({
            "max_position_pct": 100,
            "max_daily_loss_pct": 100,
            "max_drawdown_pct": 100,
            "cooldown_minutes": 0,
            "symbol_whitelist": ["BTCUSDT", "ETHUSDT"],
        })
        set_kill_switch(False, "Spot allocation test")

    def tearDown(self) -> None:
        storage_sqlite.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def policy(self, targets: list[dict] | None = None, name: str = "Core allocation") -> dict:
        return save_allocation_policy(
            name=name,
            targets=targets or [
                {"symbol": "BTCUSDT", "target_pct": 50},
                {"symbol": "ETHUSDT", "target_pct": 30},
            ],
            min_trade_notional=25,
        )["policy"]

    def test_policy_versions_are_immutable_and_idempotent(self) -> None:
        first = self.policy()
        same = self.policy()
        changed = self.policy([
            {"symbol": "BTCUSDT", "target_pct": 60},
            {"symbol": "ETHUSDT", "target_pct": 20},
        ])
        self.assertEqual(first["id"], same["id"])
        self.assertEqual(same["active_version"], 1)
        self.assertEqual(changed["active_version"], 2)
        with connect() as connection:
            versions = connection.execute(
                "SELECT * FROM spot_allocation_policy_versions WHERE policy_id = ? ORDER BY version_number",
                (first["id"],),
            ).fetchall()
        self.assertEqual(len(versions), 2)

    def test_preview_persists_plan_without_creating_transactions(self) -> None:
        policy = self.policy()
        result = create_rebalance_run(policy["id"])
        run = result["run"]
        self.assertEqual(run["status"], "draft")
        self.assertFalse(result["execution_created"])
        self.assertEqual([order["side"] for order in run["plan"]], ["buy", "buy"])
        self.assertEqual(run["metrics"]["orders_total"], 2)
        self.assertTrue(run["metrics"]["risk_ready"])
        self.assertTrue(all(item["validation_id"] is None for item in run["metrics"]["risk_preview"]))
        self.assertLess(run["metrics"]["expected_drift_pct_points"], run["metrics"]["current_drift_pct_points"])
        self.assertEqual(portfolio_snapshot()["transactions"], [])
        with connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM risk_validation_log").fetchone()[0], 0)

    def test_apply_is_idempotent_and_uses_rebalance_origin(self) -> None:
        run = create_rebalance_run(self.policy()["id"])["run"]
        applied = apply_rebalance_run(run["id"])
        replay = apply_rebalance_run(run["id"])
        self.assertEqual(applied["run"]["status"], "applied")
        self.assertTrue(replay["recovered"])
        self.assertEqual(len(applied["snapshot"]["transactions"]), 2)
        self.assertEqual(len(replay["snapshot"]["transactions"]), 2)
        self.assertTrue(all(row["origin"] == "rebalance_run" for row in replay["snapshot"]["transactions"]))
        self.assertTrue(all(row["risk_validation_id"] for row in replay["snapshot"]["transactions"]))
        validation_count = len(replay["run"]["execution"])
        with connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM risk_validation_log").fetchone()[0], validation_count)

    def test_changed_portfolio_invalidates_draft(self) -> None:
        run = create_rebalance_run(self.policy()["id"])["run"]
        execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01})
        with self.assertRaisesRegex(ValueError, "state changed"):
            apply_rebalance_run(run["id"])

    def test_sell_orders_execute_before_buys(self) -> None:
        execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1})
        policy = self.policy([{"symbol": "ETHUSDT", "target_pct": 50}], name="Rotate to ETH")
        run = create_rebalance_run(policy["id"])["run"]
        self.assertEqual(run["plan"][0]["side"], "sell")
        applied = apply_rebalance_run(run["id"])
        self.assertEqual(applied["run"]["execution"][0]["side"], "sell")
        self.assertEqual(applied["run"]["execution"][1]["side"], "buy")

    def test_applying_run_recovers_written_transaction(self) -> None:
        run = create_rebalance_run(self.policy()["id"])["run"]
        first_order = run["plan"][0]
        risk = validate_order_intent({
            "mode": "spot", "symbol": first_order["symbol"], "side": "long",
            "requested_notional": first_order["planned_notional"], "account_equity": 10_000,
            "daily_pnl": 0, "current_drawdown_pct": 0,
        })
        with connect() as connection:
            connection.execute("UPDATE spot_rebalance_runs SET status='applying' WHERE id=?", (run["id"],))
        written = execute_spot_transaction({
            "symbol": first_order["symbol"],
            "side": first_order["side"],
            "quantity": first_order["planned_quantity"],
            "origin": "rebalance_run",
            "origin_reference": f"rebalance:{run['id']}:{first_order['order_index']}:{first_order['symbol']}",
            "risk_validation_id": risk["validation_id"],
        })
        recovered = apply_rebalance_run(run["id"])
        first_execution = recovered["run"]["execution"][0]
        self.assertTrue(first_execution["recovered"])
        self.assertEqual(first_execution["transaction_id"], written["transaction_id"])
        self.assertEqual(first_execution["risk_validation_id"], risk["validation_id"])
        self.assertEqual(len(recovered["snapshot"]["transactions"]), 2)

    def test_kill_switch_rejects_buys_with_persisted_risk_evidence(self) -> None:
        run = create_rebalance_run(self.policy()["id"])["run"]
        set_kill_switch(True, "Emergency stop fixture")
        result = apply_rebalance_run(run["id"])
        self.assertEqual(result["run"]["status"], "partial")
        self.assertEqual(result["snapshot"]["transactions"], [])
        self.assertTrue(all(item["status"] == "rejected" for item in result["run"]["execution"]))
        self.assertTrue(all(item["stage"] == "risk" for item in result["run"]["execution"]))
        self.assertTrue(all(item["risk_validation_id"] for item in result["run"]["execution"]))

    def test_kill_switch_still_allows_close_only_reduction(self) -> None:
        execute_spot_transaction({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1})
        policy = self.policy([{"symbol": "ETHUSDT", "target_pct": 50}], name="Close BTC under halt")
        run = create_rebalance_run(policy["id"])["run"]
        update_risk_limits({
            "max_position_pct": 100,
            "max_daily_loss_pct": 100,
            "max_drawdown_pct": 100,
            "cooldown_minutes": 0,
            "symbol_whitelist": ["ETHUSDT"],
        })
        set_kill_switch(True, "Close-only fixture")
        result = apply_rebalance_run(run["id"])
        self.assertEqual(result["run"]["execution"][0]["side"], "sell")
        self.assertEqual(result["run"]["execution"][0]["status"], "executed")
        self.assertEqual(result["run"]["execution"][1]["status"], "rejected")

    def test_archive_blocks_new_runs_and_tables_are_in_data_center(self) -> None:
        policy = self.policy()
        archived = archive_allocation_policy(policy["id"])["policy"]
        self.assertEqual(archived["status"], "archived")
        with self.assertRaisesRegex(ValueError, "Archived"):
            create_rebalance_run(policy["id"])
        self.assertEqual(len(list_allocation_policies()["policies"]), 1)
        for dataset in ("spot_allocation_policies", "spot_allocation_policy_versions", "spot_rebalance_runs"):
            self.assertIn("rows", get_dataset_preview(dataset, 10))


if __name__ == "__main__":
    unittest.main()
