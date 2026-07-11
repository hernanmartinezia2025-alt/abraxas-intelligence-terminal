from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.storage import sqlite as storage_sqlite
from backend.app.storage.paper import account_snapshot, place_market_order
from backend.app.storage.risk import get_risk_profile, set_kill_switch
from backend.app.storage.sqlite import connect, initialize_database


class ExecutionPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = storage_sqlite.DB_PATH
        storage_sqlite.DB_PATH = Path(self.temp_dir.name) / "execution-pipeline.db"
        initialize_database()
        with connect() as connection:
            connection.execute(
                """INSERT INTO market_snapshots (
                    timestamp, symbol, price, change_24h, volume_24h,
                    fear_greed_value, fear_greed_label, risk_level, abraxas_reading
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "2026-07-11T00:00:00+00:00",
                    "BTCUSDT",
                    64_000,
                    1.0,
                    1_000_000,
                    30,
                    "Fear",
                    "normal",
                    "integration fixture",
                ),
            )

    def tearDown(self) -> None:
        storage_sqlite.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_kill_switch_rejection_links_intent_risk_and_order(self) -> None:
        result = place_market_order(
            {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.001, "bot_id": None}
        )

        self.assertEqual(result["status"], "rejected")
        self.assertFalse(result["execution_performed"])
        snapshot = account_snapshot()
        intent = snapshot["execution_intents"][0]
        self.assertEqual(intent["status"], "rejected")
        self.assertEqual(intent["risk_validation_id"], result["risk"]["validation_id"])
        self.assertEqual(intent["result_reference"], f"simulated_order:{result['order_id']}")

        validation = get_risk_profile()["validation_log"][0]
        self.assertEqual(validation["execution_intent_id"], intent["id"])
        self.assertFalse(validation["approved"])

    def test_approved_paper_order_links_intent_risk_and_fill(self) -> None:
        set_kill_switch(False, "Execution pipeline integration test")
        result = place_market_order(
            {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.001, "bot_id": None}
        )

        self.assertEqual(result["status"], "filled")
        self.assertTrue(result["execution_performed"])
        snapshot = result["account"]
        intent = snapshot["execution_intents"][0]
        self.assertEqual(intent["status"], "filled")
        self.assertEqual(intent["risk_validation_id"], result["risk"]["validation_id"])
        self.assertEqual(intent["result_reference"], f"simulated_fill:{result['fill_id']}")
        self.assertEqual(snapshot["orders"][0]["risk_validation_id"], result["risk"]["validation_id"])


if __name__ == "__main__":
    unittest.main()
