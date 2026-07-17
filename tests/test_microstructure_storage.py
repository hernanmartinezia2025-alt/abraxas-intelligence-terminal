from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.services.data_center_service import get_dataset_preview
from backend.app.storage import sqlite as storage_sqlite
from backend.app.storage.microstructure import (
    get_microstructure_status,
    list_aggregate_trades,
    save_aggregate_trades,
    save_order_book_snapshot,
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


if __name__ == "__main__":
    unittest.main()
