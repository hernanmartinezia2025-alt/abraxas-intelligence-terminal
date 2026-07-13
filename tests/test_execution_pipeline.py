from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.storage import sqlite as storage_sqlite
from backend.app.storage.paper import account_snapshot, place_market_order, reconcile_paper_runtime
from backend.app.storage.risk import get_risk_profile, set_kill_switch
from backend.app.storage.sqlite import connect, initialize_database
from backend.app.storage.proposals import claim_paper_proposal, dismiss_paper_proposal, save_paper_proposal
from backend.app.storage.signals import save_signal_evaluation
from backend.app.services.bot_service import submit_saved_bot_paper_proposal
from backend.app.services.bot_service import create_saved_bot_paper_proposal
from backend.app.storage.bots import create_bot


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
                    datetime.now(timezone.utc).isoformat(),
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
        repeated = submit_saved_bot_paper_proposal(1, proposal["id"])
        self.assertTrue(repeated["paper_result"]["recovered"])
        self.assertEqual(repeated["paper_result"]["intent_id"], result["paper_result"]["intent_id"])
        with connect() as connection:
            intent = dict(connection.execute("SELECT * FROM execution_intents WHERE id = ?", (result["paper_result"]["intent_id"],)).fetchone())
            order_count = connection.execute("SELECT COUNT(*) FROM simulated_orders").fetchone()[0]
        self.assertEqual(intent["bot_version_id"], 1)
        self.assertEqual(intent["signal_evaluation_id"], signal_id)
        self.assertEqual(intent["proposal_id"], proposal["id"])
        self.assertEqual(intent["strategy_hash"], "hash")
        self.assertEqual(order_count, 1)

    def test_accumulated_position_cannot_exceed_risk_limit(self) -> None:
        set_kill_switch(False, "Accumulated exposure integration test")

        first = place_market_order({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "bot_id": None})
        second = place_market_order({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "bot_id": None})

        self.assertEqual(first["status"], "filled")
        self.assertEqual(second["status"], "rejected")
        self.assertIn("Projected exposure", second["reason"])
        self.assertGreater(second["risk"]["metrics"]["position_pct"], 10)
        self.assertGreater(second["risk"]["metrics"]["current_position_pct"], 0)

    def test_signal_evaluation_is_idempotent_per_version_and_feature(self) -> None:
        payload = {
            "bot_id": 1, "bot_version_id": 1, "strategy_hash": "stable-hash",
            "symbol": "BTCUSDT", "timeframe": "15m", "feature_timestamp": 123,
            "signal": "hold", "entry_passed": False, "exit_passed": False,
            "conflict": False, "features": {"return_1": 0}, "trace": {"entry": [], "exit": []},
        }

        first = save_signal_evaluation(payload)
        second = save_signal_evaluation(payload)

        self.assertEqual(first["id"], second["id"])
        with connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM strategy_signal_evaluations").fetchone()[0]
        self.assertEqual(count, 1)

    def test_claimed_proposal_cannot_be_dismissed(self) -> None:
        with connect() as connection:
            signal_id = connection.execute(
                """INSERT INTO strategy_signal_evaluations (
                   bot_id, bot_version_id, strategy_hash, symbol, timeframe, feature_timestamp,
                   signal, entry_passed, exit_passed, features_json, trace_json, evaluated_at
                   ) VALUES (1, 1, 'claim-hash', 'BTCUSDT', '15m', 2, 'entry_candidate', 1, 0, '{}', '{}', ?)""",
                ("2026-07-11T00:00:00+00:00",),
            ).lastrowid
        proposal = save_paper_proposal({
            "signal_evaluation_id": signal_id, "bot_id": 1, "bot_version_id": 1,
            "symbol": "BTCUSDT", "action": "buy", "quantity": 0.001,
            "reference_price": 64_000, "proposed_notional": 64, "reason": "claim test",
        })

        claim_paper_proposal(proposal["id"], 1)

        with self.assertRaisesRegex(ValueError, "pending"):
            dismiss_paper_proposal(proposal["id"], 1)

    def test_concurrent_orders_respect_cumulative_position_limit(self) -> None:
        set_kill_switch(False, "Concurrent exposure integration test")

        def submit() -> dict:
            return place_market_order({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "bot_id": None})

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit(), range(2)))

        self.assertEqual(sorted(result["status"] for result in results), ["filled", "rejected"])
        snapshot = account_snapshot()
        self.assertAlmostEqual(snapshot["positions"][0]["quantity"], 0.01)

    def test_allocations_keep_bot_cost_basis_and_close_only_exit(self) -> None:
        set_kill_switch(False, "Allocation accounting test")
        with connect() as connection:
            connection.execute(
                """INSERT INTO bots (id, name, description, status, mode, base_symbol, timeframe,
                   risk_profile, created_at, updated_at) VALUES
                   (2, 'second-bot', '', 'draft', 'research', 'BTCUSDT', '15m', 'balanced', ?, ?)""",
                ("2026-07-11T00:00:00+00:00", "2026-07-11T00:00:00+00:00"),
            )
            connection.execute(
                "INSERT INTO bot_versions (id, bot_id, version, strategy_json, notes, created_at) VALUES (2, 2, 1, '{}', '', ?)",
                ("2026-07-11T00:00:00+00:00",),
            )
        first = place_market_order({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.005, "bot_id": 1, "bot_version_id": 1, "strategy_hash": "one"})
        with connect() as connection:
            connection.execute(
                """INSERT INTO market_snapshots (timestamp, symbol, price, change_24h, volume_24h,
                   fear_greed_value, fear_greed_label, risk_level, abraxas_reading)
                   VALUES (?, 'BTCUSDT', 66000, 1, 1, 30, 'Fear', 'normal', 'test')""",
                ((datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(),),
            )
        second = place_market_order({"symbol": "BTCUSDT", "side": "buy", "quantity": 0.005, "bot_id": 2, "bot_version_id": 2, "strategy_hash": "two"})
        set_kill_switch(True, "Close-only must remain possible")
        with connect() as connection:
            connection.execute(
                """INSERT INTO market_snapshots (timestamp, symbol, price, change_24h, volume_24h,
                   fear_greed_value, fear_greed_label, risk_level, abraxas_reading)
                   VALUES (?, 'BTCUSDT', 65000, 1, 1, 30, 'Fear', 'normal', 'test')""",
                ((datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat(),),
            )
        closed = place_market_order({"symbol": "BTCUSDT", "side": "sell", "quantity": 0.005, "bot_id": 1, "bot_version_id": 1, "strategy_hash": "one"})

        self.assertEqual(first["status"], "filled")
        self.assertEqual(second["status"], "filled")
        self.assertEqual(closed["status"], "filled")
        self.assertTrue(closed["risk"]["metrics"]["close_only"])
        with connect() as connection:
            bot_one = dict(connection.execute("SELECT * FROM simulated_position_allocations WHERE owner_key LIKE 'bot:1:%'").fetchone())
            bot_two = dict(connection.execute("SELECT * FROM simulated_position_allocations WHERE owner_key LIKE 'bot:2:%'").fetchone())
            global_position = dict(connection.execute("SELECT * FROM simulated_positions WHERE symbol = 'BTCUSDT'").fetchone())
        self.assertAlmostEqual(bot_one["quantity"], 0)
        self.assertAlmostEqual(bot_two["average_price"], 66000)
        self.assertAlmostEqual(global_position["average_price"], 66000)
        self.assertAlmostEqual(bot_one["realized_pnl"], 4.355, places=6)

    def test_exit_candidate_closes_exact_bot_allocation(self) -> None:
        strategy = {
            "engine": "rules",
            "entry": [{"field": "return_5", "operator": ">", "value": 0}],
            "exit": [{"field": "return_1", "operator": "<", "value": -0.5}],
            "risk": {"max_position_pct": 5, "stop_loss_pct": 2, "take_profit_pct": 4},
        }
        detail = create_bot({"name": "exit-runtime-bot", "base_symbol": "BTCUSDT", "timeframe": "15m", "strategy": strategy})
        bot = detail["bot"]
        version = detail["versions"][0]
        set_kill_switch(False, "Open allocation before close-only test")
        opened = place_market_order({
            "symbol": "BTCUSDT", "side": "buy", "quantity": 0.001, "bot_id": bot["id"],
            "bot_version_id": version["id"], "strategy_hash": version["strategy_hash"],
        })
        evaluation = save_signal_evaluation({
            "bot_id": bot["id"], "bot_version_id": version["id"], "strategy_hash": version["strategy_hash"],
            "symbol": "BTCUSDT", "timeframe": "15m", "feature_timestamp": 999,
            "signal": "exit_candidate", "entry_passed": False, "exit_passed": True, "conflict": False,
            "trigger_reason": "strategy_exit", "features": {"return_1": -1}, "trace": {"entry": [], "exit": []},
        })
        proposal = create_saved_bot_paper_proposal(bot["id"], evaluation["id"])
        set_kill_switch(True, "Close-only proposal must still close exposure")
        submitted = submit_saved_bot_paper_proposal(bot["id"], proposal["id"])

        self.assertEqual(opened["status"], "filled")
        self.assertEqual(proposal["action"], "sell")
        self.assertEqual(proposal["quantity"], 0.001)
        self.assertIsNotNone(proposal["allocation_id"])
        self.assertEqual(submitted["paper_result"]["status"], "filled")
        self.assertTrue(submitted["paper_result"]["risk"]["metrics"]["close_only"])
        with connect() as connection:
            allocation = connection.execute("SELECT quantity FROM simulated_position_allocations WHERE id = ?", (proposal["allocation_id"],)).fetchone()
        self.assertAlmostEqual(allocation["quantity"], 0)

    def test_reconciler_releases_stale_lease_without_execution(self) -> None:
        with connect() as connection:
            signal_id = connection.execute(
                """INSERT INTO strategy_signal_evaluations (
                   bot_id, bot_version_id, strategy_hash, symbol, timeframe, feature_timestamp,
                   signal, entry_passed, exit_passed, features_json, trace_json, evaluated_at
                   ) VALUES (1, 1, 'stale-hash', 'BTCUSDT', '15m', 33, 'entry_candidate', 1, 0, '{}', '{}', ?)""",
                (datetime.now(timezone.utc).isoformat(),),
            ).lastrowid
        proposal = save_paper_proposal({
            "signal_evaluation_id": signal_id, "bot_id": 1, "bot_version_id": 1,
            "symbol": "BTCUSDT", "action": "buy", "quantity": 0.001,
            "reference_price": 64_000, "proposed_notional": 64, "reason": "stale lease test",
        })
        claim_paper_proposal(proposal["id"], 1)
        with connect() as connection:
            connection.execute(
                "UPDATE paper_order_proposals SET claimed_at = ? WHERE id = ?",
                ((datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), proposal["id"]),
            )

        result = reconcile_paper_runtime(stale_after_seconds=60)

        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["leases_released"], 1)
        with connect() as connection:
            repaired = dict(connection.execute("SELECT * FROM paper_order_proposals WHERE id = ?", (proposal["id"],)).fetchone())
            order_count = connection.execute("SELECT COUNT(*) FROM simulated_orders").fetchone()[0]
        self.assertIsNone(repaired["claim_token"])
        self.assertEqual(repaired["status"], "pending")
        self.assertEqual(order_count, 0)


if __name__ == "__main__":
    unittest.main()
