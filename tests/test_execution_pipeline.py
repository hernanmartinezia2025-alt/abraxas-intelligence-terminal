from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.storage import sqlite as storage_sqlite
from backend.app.storage.paper import account_snapshot, place_market_order
from backend.app.storage.risk import get_risk_profile, set_kill_switch
from backend.app.storage.sqlite import connect, initialize_database
from backend.app.storage.proposals import save_paper_proposal
from backend.app.services.bot_service import submit_saved_bot_paper_proposal


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
            connection.execute(
                """INSERT INTO bots (id, name, description, status, mode, base_symbol, timeframe,
                   risk_profile, created_at, updated_at) VALUES
                   (1, 'proposal-bot', '', 'draft', 'research', 'BTCUSDT', '15m', 'balanced', ?, ?)""",
                ("2026-07-11T00:00:00+00:00", "2026-07-11T00:00:00+00:00"),
            )
            connection.execute(
                """INSERT INTO bot_versions (id, bot_id, version, strategy_json, notes, created_at)
                   VALUES (1, 1, 1, '{}', '', ?)""",
                ("2026-07-11T00:00:00+00:00",),
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

    def test_proposal_submission_is_risk_gated_and_cannot_repeat(self) -> None:
        with connect() as connection:
            signal_id = connection.execute(
                """INSERT INTO strategy_signal_evaluations (
                   bot_id, bot_version_id, strategy_hash, symbol, timeframe, feature_timestamp,
                   signal, entry_passed, exit_passed, features_json, trace_json, evaluated_at
                   ) VALUES (1, 1, 'hash', 'BTCUSDT', '15m', 1, 'entry_candidate', 1, 0, '{}', '{}', ?)""",
                ("2026-07-11T00:00:00+00:00",),
            ).lastrowid
        proposal = save_paper_proposal({
            "signal_evaluation_id": signal_id, "bot_id": 1, "bot_version_id": 1,
            "symbol": "BTCUSDT", "action": "buy", "quantity": 0.001,
            "reference_price": 64_000, "proposed_notional": 64,
            "reason": "integration test",
        })

        result = submit_saved_bot_paper_proposal(1, proposal["id"])

        self.assertEqual(result["proposal"]["status"], "submitted")
        self.assertEqual(result["paper_result"]["status"], "rejected")
        self.assertEqual(result["proposal"]["execution_intent_id"], result["paper_result"]["intent_id"])
        self.assertEqual(result["proposal"]["risk_validation_id"], result["paper_result"]["risk"]["validation_id"])
        with self.assertRaisesRegex(ValueError, "already processed"):
            submit_saved_bot_paper_proposal(1, proposal["id"])

    def test_accumulated_position_cannot_exceed_risk_limit(self) -> None:
        set_kill_switch(False, "Accumulated exposure integration test")

        first = place_market_order({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "bot_id": None})
        second = place_market_order({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "bot_id": None})

        self.assertEqual(first["status"], "filled")
        self.assertEqual(second["status"], "rejected")
        self.assertIn("Projected exposure", second["reason"])
        self.assertGreater(second["risk"]["metrics"]["position_pct"], 10)
        self.assertGreater(second["risk"]["metrics"]["current_position_pct"], 0)


if __name__ == "__main__":
    unittest.main()
