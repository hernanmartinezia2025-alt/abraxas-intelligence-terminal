from __future__ import annotations

import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.services.data_center_service import get_dataset_preview
from backend.app.storage import sqlite as storage_sqlite
from backend.app.storage.spot_dca import (
    advance_schedule,
    create_dca_plan,
    execute_due_dca_plan,
    list_dca_plans,
    preview_dca_plan,
    set_dca_plan_status,
)
from backend.app.storage.spot_portfolio import execute_spot_transaction
from backend.app.storage.sqlite import connect, initialize_database


class SpotDcaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = storage_sqlite.DB_PATH
        storage_sqlite.DB_PATH = Path(self.temp_dir.name) / "spot-dca.db"
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

    def create_plan(self, **overrides) -> dict:
        payload = {
            "name": "BTC weekly accumulation",
            "symbol": "BTCUSDT",
            "budget_amount": 1000,
            "frequency": "weekly",
            "interval_count": 1,
            "allocation_limit_pct": 80,
            "next_run_at": "2025-01-01T00:00:00+00:00",
        }
        payload.update(overrides)
        return create_dca_plan(payload)["plan"]

    def test_due_plan_executes_one_idempotent_spot_transaction(self) -> None:
        plan = self.create_plan(next_run_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        preview = preview_dca_plan(plan["id"])
        self.assertTrue(preview["due"])
        self.assertTrue(preview["allowed"])
        self.assertFalse(preview["execution_created"])

        result = execute_due_dca_plan(plan["id"])
        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["transaction"]["origin"], "dca_plan")
        self.assertTrue(result["transaction"]["origin_reference"].startswith(f"dca:{plan['id']}:"))
        self.assertEqual(len(result["snapshot"]["transactions"]), 1)
        self.assertGreater(result["plan"]["next_run_at"], plan["next_run_at"])
        with self.assertRaisesRegex(ValueError, "not due"):
            execute_due_dca_plan(plan["id"])

        plans = list_dca_plans()
        self.assertEqual(len(plans["executions"]), 1)
        self.assertEqual(plans["executions"][0]["status"], "executed")
        self.assertEqual(len(get_dataset_preview("spot_dca_plans", 10)["rows"]), 1)
        self.assertEqual(len(get_dataset_preview("spot_dca_executions", 10)["rows"]), 1)

    def test_allocation_limit_rejects_without_advancing_schedule(self) -> None:
        plan = self.create_plan(budget_amount=5000, allocation_limit_pct=10)
        first = execute_due_dca_plan(plan["id"])
        second = execute_due_dca_plan(plan["id"])
        self.assertEqual(first["status"], "rejected")
        self.assertIn("exceeds", first["execution"]["reason"])
        self.assertEqual(second["execution"]["id"], first["execution"]["id"])
        self.assertEqual(second["plan"]["next_run_at"], plan["next_run_at"])
        self.assertEqual(second["snapshot"]["transactions"], [])

    def test_pause_blocks_preview_and_execution(self) -> None:
        plan = self.create_plan()
        paused = set_dca_plan_status(plan["id"], "paused")["plan"]
        self.assertFalse(paused["due"])
        preview = preview_dca_plan(plan["id"])
        self.assertFalse(preview["allowed"])
        self.assertEqual(preview["reason"], "Plan is paused")
        with self.assertRaisesRegex(ValueError, "paused"):
            execute_due_dca_plan(plan["id"])

    def test_transaction_origin_reference_recovers_without_double_buy(self) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": 0.01,
            "origin": "dca_plan",
            "origin_reference": "dca:99:fixture",
        }
        first = execute_spot_transaction(payload)
        second = execute_spot_transaction(payload)
        self.assertFalse(first["recovered"])
        self.assertTrue(second["recovered"])
        self.assertEqual(first["transaction_id"], second["transaction_id"])
        self.assertEqual(len(second["snapshot"]["transactions"]), 1)

    def test_plan_recovers_transaction_written_before_schedule_advance(self) -> None:
        plan = self.create_plan(next_run_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        preview = preview_dca_plan(plan["id"])
        origin_reference = f"dca:{plan['id']}:{plan['next_run_at']}"
        written = execute_spot_transaction({
            "symbol": plan["symbol"],
            "side": "buy",
            "quantity": preview["quote"]["quantity"],
            "origin": "dca_plan",
            "origin_reference": origin_reference,
        })
        recovered = execute_due_dca_plan(plan["id"])
        self.assertEqual(recovered["transaction"]["id"], written["transaction_id"])
        self.assertTrue(recovered["recovered_transaction"])
        self.assertEqual(len(recovered["snapshot"]["transactions"]), 1)
        self.assertEqual(len(list_dca_plans()["executions"]), 1)

    def test_monthly_schedule_clamps_end_of_month(self) -> None:
        january = datetime(2025, 1, 31, 12, tzinfo=timezone.utc)
        february = advance_schedule(january, "monthly", 1)
        self.assertEqual((february.year, february.month, february.day), (2025, 2, 28))

    def test_legacy_spot_transactions_migrate_before_idempotency_index(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy-spot.db"
        storage_sqlite.DB_PATH = legacy_path
        connection = sqlite3.connect(legacy_path)
        try:
            connection.execute(
                """CREATE TABLE spot_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, portfolio_id INTEGER NOT NULL,
                symbol TEXT NOT NULL, side TEXT NOT NULL, quantity REAL NOT NULL,
                price REAL NOT NULL, notional REAL NOT NULL, fee REAL NOT NULL,
                realized_pnl REAL NOT NULL DEFAULT 0, price_timestamp TEXT NOT NULL,
                source TEXT NOT NULL, notes TEXT, cycle_number INTEGER NOT NULL DEFAULT 1,
                executed_at TEXT NOT NULL)"""
            )
            connection.commit()
        finally:
            connection.close()
        initialize_database()
        with connect() as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(spot_transactions)").fetchall()}
            indexes = {row["name"] for row in connection.execute("PRAGMA index_list(spot_transactions)").fetchall()}
        self.assertIn("origin", columns)
        self.assertIn("origin_reference", columns)
        self.assertIn("idx_spot_transactions_origin_reference", indexes)


if __name__ == "__main__":
    unittest.main()
