from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.services.data_center_service import get_dataset_preview
from backend.app.market.local_order_book import DepthSequenceGap, LocalOrderBook
from backend.app.services.microstructure_collector import normalize_agg_trade_event, normalize_depth_event
from backend.app.services.microstructure_service import replay_order_book
from backend.app.storage import sqlite as storage_sqlite
from backend.app.storage.microstructure import (
    get_microstructure_status,
    list_aggregate_trades,
    save_aggregate_trades,
    save_order_book_deltas,
    save_order_book_snapshot,
    start_collector_run,
    latest_collector_run,
    reconcile_interrupted_collectors,
)


class MicrostructureStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = storage_sqlite.DB_PATH
        storage_sqlite.DB_PATH = Path(self.temp_dir.name) / "microstructure.db"
        storage_sqlite.initialize_database()

    def tearDown(self) -> None:
        storage_sqlite.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_aggregate_trade_storage_is_idempotent(self) -> None:
        trades = [
            {
                "symbol": "BTCUSDT",
                "aggregate_trade_id": index,
                "first_trade_id": index * 2,
                "last_trade_id": index * 2 + 1,
                "event_time": 1_700_000_000_000 + index,
                "price": 50_000 + index,
                "quantity": 0.1,
                "quote_quantity": 5_000,
                "buyer_is_maker": index == 0,
                "aggressor_side": "sell" if index == 0 else "buy",
                "source": "test",
                "fetched_at": "2026-01-01T00:00:00Z",
            }
            for index in range(2)
        ]
        self.assertEqual(save_aggregate_trades(trades), 2)
        self.assertEqual(save_aggregate_trades(trades), 0)
        persisted = list_aggregate_trades("BTCUSDT", 1_700_000_000_000, 1_700_000_000_100)
        self.assertEqual(len(persisted), 2)
        self.assertEqual(persisted[0]["aggressor_side"], "sell")

    def test_depth_snapshot_normalizes_levels_and_reaches_data_center(self) -> None:
        snapshot = save_order_book_snapshot(
            {
                "symbol": "BTCUSDT",
                "source": "test",
                "last_update_id": 42,
                "best_bid": 100,
                "best_ask": 101,
                "spread": 1,
                "spread_percent": 0.995,
                "mid_price": 100.5,
                "fetched_at": "2026-01-01T00:00:00Z",
                "bids": [{"price": 100, "quantity": 2, "notional": 200}],
                "asks": [{"price": 101, "quantity": 3, "notional": 303}],
            }
        )
        self.assertEqual(snapshot["levels_saved"], 2)
        status = get_microstructure_status("BTCUSDT")
        self.assertEqual(status["order_book_snapshots"]["row_count"], 1)
        preview = get_dataset_preview("order_book_levels", limit=5)
        self.assertTrue(preview["dataset"]["exists"])
        self.assertEqual(len(preview["rows"]), 2)

    def test_local_book_applies_sequence_and_detects_gap(self) -> None:
        book = LocalOrderBook.from_snapshot(
            {
                "symbol": "BTCUSDT",
                "last_update_id": 100,
                "bids": [{"price": 100, "quantity": 2}],
                "asks": [{"price": 101, "quantity": 3}],
            }
        )
        applied = book.apply(
            {
                "first_update_id": 101,
                "final_update_id": 102,
                "bid_changes": [["100", "0"], ["99.5", "4"]],
                "ask_changes": [["101", "1"]],
            }
        )
        self.assertTrue(applied)
        self.assertNotIn(100.0, book.bids)
        self.assertEqual(book.bids[99.5], 4.0)
        self.assertEqual(book.last_update_id, 102)
        with self.assertRaises(DepthSequenceGap):
            book.apply(
                {
                    "first_update_id": 104,
                    "final_update_id": 105,
                    "bid_changes": [],
                    "ask_changes": [],
                }
            )

    def test_stream_events_are_normalized_and_deltas_are_idempotent(self) -> None:
        trade = normalize_agg_trade_event(
            {"s": "BTCUSDT", "a": 12, "f": 20, "l": 21, "T": 1_700_000_000_000,
             "p": "100.5", "q": "2", "m": False, "M": True}
        )
        self.assertEqual(trade["aggressor_side"], "buy")
        self.assertEqual(trade["quote_quantity"], 201.0)
        delta = normalize_depth_event(
            {"s": "BTCUSDT", "E": 1_700_000_000_001, "U": 101, "u": 102,
             "b": [["100", "2"]], "a": [["101", "0"]]}
        )
        self.assertEqual(save_order_book_deltas([delta]), 1)
        self.assertEqual(save_order_book_deltas([delta]), 0)
        status = get_microstructure_status("BTCUSDT")
        self.assertEqual(status["order_book_deltas"]["row_count"], 1)
        preview = get_dataset_preview("order_book_deltas", limit=5)
        self.assertEqual(len(preview["rows"]), 1)

    def test_restart_marks_running_collector_as_interrupted(self) -> None:
        run_id = start_collector_run(["BTCUSDT"], {"snapshot_interval_seconds": 10})
        self.assertEqual(run_id, 1)
        self.assertEqual(reconcile_interrupted_collectors(), 1)
        run = latest_collector_run()
        self.assertEqual(run["status"], "interrupted")
        self.assertIsNotNone(run["stopped_at"])

    def test_replay_reconstructs_bounded_book_with_complete_sequence(self) -> None:
        save_order_book_snapshot(
            {
                "symbol": "BTCUSDT",
                "source": "binance_depth_stream_local_book",
                "last_update_id": 42,
                "best_bid": 100,
                "best_ask": 101,
                "spread": 1,
                "spread_percent": 0.995,
                "mid_price": 100.5,
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "bids": [{"price": 100, "quantity": 2, "notional": 200}],
                "asks": [{"price": 101, "quantity": 3, "notional": 303}],
            }
        )
        deltas = [
            {
                "symbol": "BTCUSDT", "event_time": 1_767_225_601_000,
                "first_update_id": 43, "final_update_id": 43,
                "bid_changes": [["100", "1"]], "ask_changes": [],
                "source": "test", "received_at": "2026-01-01T00:00:01+00:00",
            },
            {
                "symbol": "BTCUSDT", "event_time": 1_767_225_602_000,
                "first_update_id": 44, "final_update_id": 44,
                "bid_changes": [["99", "4"]], "ask_changes": [["101", "0"], ["102", "2"]],
                "source": "test", "received_at": "2026-01-01T00:00:02+00:00",
            },
        ]
        self.assertEqual(save_order_book_deltas(deltas), 2)
        replay = replay_order_book("BTCUSDT", 1_767_225_602_000, levels=20)
        self.assertTrue(replay["replay"]["sequence_complete"])
        self.assertEqual(replay["replay"]["deltas_applied"], 2)
        self.assertEqual(replay["book"]["best_bid"], 100.0)
        self.assertEqual(replay["book"]["best_ask"], 102.0)
        self.assertEqual(replay["replay"]["final_update_id"], 44)


if __name__ == "__main__":
    unittest.main()
