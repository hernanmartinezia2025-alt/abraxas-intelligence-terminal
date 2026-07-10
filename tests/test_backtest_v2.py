from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.analytics.backtest import run_backtest
from backend.app.services.bot_service import feature_rows_with_close
from backend.app.services.data_center_service import export_dataset_csv, get_dataset_preview
from backend.app.storage import sqlite as sqlite_storage
from backend.app.storage.backtests import get_backtest, save_backtest_run


def sample_rows(count: int = 80, entry_index: int = 10, exit_index: int | None = 20) -> list[dict]:
    rows = []
    for index in range(count):
        open_price = 100 + index * 0.2
        close_price = open_price + 0.1
        rows.append(
            {
                "timestamp": 1_700_000_000_000 + index * 60_000,
                "open": open_price,
                "high": close_price + 0.2,
                "low": open_price - 0.2,
                "close": close_price,
                "entry_signal": 1 if index == entry_index else 0,
                "exit_signal": 1 if exit_index is not None and index == exit_index else 0,
            }
        )
    return rows


BOT = {"id": 1, "base_symbol": "BTCUSDT", "timeframe": "1m"}
VERSION = {
    "id": 1,
    "strategy": {
        "entry": [{"field": "entry_signal", "operator": ">", "value": 0}],
        "exit": [{"field": "exit_signal", "operator": ">", "value": 0}],
        "risk": {"max_position_pct": 50, "stop_loss_pct": 50, "take_profit_pct": 50},
    },
}


class BacktestV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = sqlite_storage.DB_PATH
        sqlite_storage.DB_PATH = Path(self.temp_dir.name) / "abraxas-test.db"
        sqlite_storage.initialize_database()
        with sqlite_storage.connect() as connection:
            connection.execute(
                """
                INSERT INTO bots (
                    id, name, description, status, mode, base_symbol, timeframe,
                    risk_profile, created_at, updated_at
                ) VALUES (1, 'test-bot', '', 'draft', 'research', 'BTCUSDT', '1m',
                          'balanced', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                """
            )
            connection.execute(
                """
                INSERT INTO bot_versions (id, bot_id, version, strategy_json, notes, created_at)
                VALUES (1, 1, 1, '{}', '', '2026-01-01T00:00:00Z')
                """
            )

    def tearDown(self) -> None:
        sqlite_storage.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_next_bar_execution_and_net_accounting(self) -> None:
        rows = sample_rows()
        result = run_backtest(
            bot=BOT,
            version=VERSION,
            rows=rows,
            initial_equity=10_000,
            fee_pct=0.1,
            slippage_pct=0.05,
            requested_limit=80,
        )

        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry_signal_timestamp"], rows[10]["timestamp"])
        self.assertEqual(trade["entry_timestamp"], rows[11]["timestamp"])
        self.assertEqual(trade["exit_signal_timestamp"], rows[20]["timestamp"])
        self.assertEqual(trade["exit_timestamp"], rows[21]["timestamp"])
        self.assertAlmostEqual(trade["entry_price"], rows[11]["open"] * 1.0005, places=7)
        self.assertAlmostEqual(result["final_equity"] - result["initial_equity"], trade["pnl"], places=3)
        self.assertEqual(len(result["equity_curve"]), len({point["timestamp"] for point in result["equity_curve"]}))
        self.assertEqual(result["metrics"]["execution_model"], "signal_close_fill_next_open")
        self.assertIsNotNone(result["metrics"]["benchmark_roi_pct"])

    def test_forced_exit_replaces_last_equity_point(self) -> None:
        rows = sample_rows(entry_index=70, exit_index=None)
        result = run_backtest(bot=BOT, version=VERSION, rows=rows)

        self.assertTrue(result["trades"][0]["forced_exit"])
        self.assertEqual(result["trades"][0]["exit_reason"], "end_of_data")
        self.assertEqual(len(result["equity_curve"]), len(rows))
        self.assertEqual(len(result["equity_curve"]), len({point["timestamp"] for point in result["equity_curve"]}))
        self.assertFalse(result["equity_curve"][-1]["in_position"])

    def test_full_allocation_reserves_entry_fee_and_never_creates_negative_long(self) -> None:
        rows = sample_rows(count=80, entry_index=1, exit_index=None)
        for row in rows:
            row["entry_signal"] = 0
            row["exit_signal"] = 0
            row["open"] = 100.0
            row["high"] = 100.0
            row["low"] = 100.0
            row["close"] = 100.0
        rows[1]["entry_signal"] = 1
        rows[2].update({"low": 1.0, "close": 1.0})
        rows[3].update({"open": 1.0, "low": 1.0, "close": 1.0, "entry_signal": 1})
        rows[5]["exit_signal"] = 1

        version = {
            **VERSION,
            "strategy": {
                **VERSION["strategy"],
                "risk": {"max_position_pct": 100, "stop_loss_pct": 50, "take_profit_pct": 50},
            },
        }
        result = run_backtest(
            bot=BOT,
            version=version,
            rows=rows,
            initial_equity=100,
            fee_pct=5,
            slippage_pct=0,
        )

        self.assertGreaterEqual(len(result["trades"]), 2)
        self.assertTrue(all(trade["quantity"] > 0 for trade in result["trades"]))
        self.assertTrue(all(point["equity"] >= 0 for point in result["equity_curve"]))
        self.assertGreaterEqual(result["final_equity"], 0)

    def test_feature_loader_fetches_warmup_and_excludes_open_candle(self) -> None:
        candles = []
        for index in range(81):
            timestamp = 1_700_000_000_000 + index * 60_000
            candles.append(
                {
                    "timestamp": timestamp,
                    "close_time": 9_999_999_999_999 if index == 80 else timestamp + 59_999,
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100,
                }
            )
        features = [{"timestamp": candle["timestamp"], "return_1": 0} for candle in candles[20:]]
        payload = {
            "source": "binance",
            "served_from": "live_and_cached",
            "candles": candles,
        }

        with patch("backend.app.services.bot_service.get_candles", return_value=payload) as get_candles_mock:
            with patch("backend.app.services.bot_service.latest_asset_features", return_value=features):
                rows, context = feature_rows_with_close("BTCUSDT", "1m", 60)

        self.assertEqual(get_candles_mock.call_args.kwargs["limit"], 81)
        self.assertEqual(len(rows), 60)
        self.assertEqual(context["feature_warmup_bars"], 20)
        self.assertEqual(context["open_candles_excluded"], 1)

    def test_save_dual_writes_normalized_tables_and_data_center(self) -> None:
        result = run_backtest(bot=BOT, version=VERSION, rows=sample_rows())
        backtest_id = save_backtest_run(result)
        detail = get_backtest(backtest_id)

        with sqlite_storage.connect() as connection:
            trade_count = connection.execute(
                "SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = ?", (backtest_id,)
            ).fetchone()[0]
            equity_count = connection.execute(
                "SELECT COUNT(*) FROM backtest_equity WHERE backtest_id = ?", (backtest_id,)
            ).fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

        self.assertEqual(trade_count, len(result["trades"]))
        self.assertEqual(equity_count, len(result["equity_curve"]))
        self.assertEqual(detail["trades"][0]["pnl"], result["trades"][0]["pnl"])
        self.assertEqual(detail["equity_curve"][0]["benchmark_equity"], result["equity_curve"][0]["benchmark_equity"])
        self.assertEqual(foreign_keys, 1)

        trade_preview = get_dataset_preview("backtest_trades", limit=10)
        equity_csv = export_dataset_csv("backtest_equity", limit=10)
        self.assertEqual(trade_preview["dataset"]["status"], "ready")
        self.assertIn("pnl", trade_preview["rows"][0])
        self.assertIn("benchmark_equity", equity_csv.splitlines()[0])

    def test_legacy_json_backfill_is_idempotent(self) -> None:
        legacy_trade = {
            "entry_timestamp": 1_700_000_000_000,
            "exit_timestamp": 1_700_000_060_000,
            "entry_price": 100,
            "exit_price": 101,
            "quantity": 1,
            "pnl": 1,
            "return_pct": 1,
            "forced_exit": True,
        }
        legacy_equity = [
            {"timestamp": 1_700_000_000_000, "equity": 10_000, "close": 100, "in_position": True},
            {"timestamp": 1_700_000_000_000, "equity": 10_001, "close": 101, "in_position": False},
        ]
        with sqlite_storage.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO backtest_runs (
                    bot_id, bot_version_id, symbol, timeframe, input_start, input_end,
                    initial_equity, final_equity, roi_pct, max_drawdown_pct,
                    total_trades, win_rate_pct, profit_factor, metrics_json,
                    trades_json, equity_curve_json, created_at
                ) VALUES (1, 1, 'BTCUSDT', '1m', 1, 2, 10000, 10001, 0.01, 0,
                          1, 100, 0, '{}', ?, ?, '2026-01-01T00:00:00Z')
                """,
                (json.dumps([legacy_trade]), json.dumps(legacy_equity)),
            )
            backtest_id = int(cursor.lastrowid)
            connection.execute("PRAGMA user_version = 0")

        sqlite_storage.initialize_database()
        sqlite_storage.initialize_database()
        with sqlite_storage.connect() as connection:
            trades = connection.execute(
                "SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = ?", (backtest_id,)
            ).fetchone()[0]
            equity = connection.execute(
                "SELECT COUNT(*) FROM backtest_equity WHERE backtest_id = ?", (backtest_id,)
            ).fetchone()[0]

        self.assertEqual(trades, 1)
        self.assertEqual(equity, 2)

    def test_corrupt_legacy_payload_does_not_block_initialization(self) -> None:
        with sqlite_storage.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO backtest_runs (
                    bot_id, bot_version_id, symbol, timeframe, input_start, input_end,
                    initial_equity, final_equity, roi_pct, max_drawdown_pct,
                    total_trades, win_rate_pct, profit_factor, metrics_json,
                    trades_json, equity_curve_json, created_at
                ) VALUES (1, 1, 'BTCUSDT', '1m', 1, 2, 10000, 10000, 0, 0,
                          0, 0, NULL, '{}', 'not-json', '{bad', '2026-01-01T00:00:00Z')
                """
            )
            backtest_id = int(cursor.lastrowid)
            connection.execute("PRAGMA user_version = 0")

        sqlite_storage.initialize_database()
        with sqlite_storage.connect() as connection:
            trade_count = connection.execute(
                "SELECT COUNT(*) FROM backtest_trades WHERE backtest_id = ?", (backtest_id,)
            ).fetchone()[0]
            equity_count = connection.execute(
                "SELECT COUNT(*) FROM backtest_equity WHERE backtest_id = ?", (backtest_id,)
            ).fetchone()[0]

        self.assertEqual(trade_count, 0)
        self.assertEqual(equity_count, 0)

    def test_profit_factor_null_is_consistent_in_sqlite_and_api(self) -> None:
        result = run_backtest(bot=BOT, version=VERSION, rows=sample_rows())
        self.assertIsNone(result["metrics"]["profit_factor"])
        backtest_id = save_backtest_run(result)

        with sqlite_storage.connect() as connection:
            stored = connection.execute(
                "SELECT profit_factor FROM backtest_runs WHERE id = ?", (backtest_id,)
            ).fetchone()[0]

        self.assertIsNone(stored)
        self.assertIsNone(get_backtest(backtest_id)["profit_factor"])

    def test_integrity_trigger_rejects_child_with_mismatched_parent(self) -> None:
        backtest_id = save_backtest_run(run_backtest(bot=BOT, version=VERSION, rows=sample_rows()))
        with sqlite_storage.connect() as connection:
            connection.execute(
                """
                INSERT INTO bots (
                    id, name, description, status, mode, base_symbol, timeframe,
                    risk_profile, created_at, updated_at
                ) VALUES (2, 'other-bot', '', 'draft', 'research', 'ETHUSDT', '1m',
                          'balanced', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
                """
            )
            connection.execute(
                """
                INSERT INTO bot_versions (id, bot_id, version, strategy_json, notes, created_at)
                VALUES (2, 2, 1, '{}', '', '2026-01-01T00:00:00Z')
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO backtest_trades (
                        backtest_id, bot_id, bot_version_id, trade_index, side,
                        entry_timestamp, exit_timestamp, entry_price, exit_price,
                        quantity, pnl, return_pct, forced_exit, created_at
                    ) VALUES (?, 2, 2, 99, 'long', 1, 2, 100, 101, 1, 1, 1, 0,
                              '2026-01-01T00:00:00Z')
                    """,
                    (backtest_id,),
                )

    def test_v1_schema_migration_makes_profit_factor_nullable(self) -> None:
        with sqlite_storage.connect() as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TABLE backtest_equity")
            connection.execute("DROP TABLE backtest_trades")
            connection.execute("DROP TABLE backtest_runs")
            connection.execute(
                """
                CREATE TABLE backtest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id INTEGER NOT NULL,
                    bot_version_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    input_start INTEGER,
                    input_end INTEGER,
                    initial_equity REAL NOT NULL,
                    final_equity REAL NOT NULL,
                    roi_pct REAL NOT NULL,
                    max_drawdown_pct REAL NOT NULL,
                    total_trades INTEGER NOT NULL,
                    win_rate_pct REAL NOT NULL,
                    profit_factor REAL NOT NULL,
                    metrics_json TEXT NOT NULL,
                    trades_json TEXT NOT NULL,
                    equity_curve_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO backtest_runs (
                    bot_id, bot_version_id, symbol, timeframe, initial_equity,
                    final_equity, roi_pct, max_drawdown_pct, total_trades,
                    win_rate_pct, profit_factor, metrics_json, trades_json,
                    equity_curve_json, created_at
                ) VALUES (1, 1, 'BTCUSDT', '1m', 10000, 10000, 0, 0, 0, 0,
                          0, '{}', '[]', '[]', '2026-01-01T00:00:00Z')
                """
            )
            connection.execute("PRAGMA user_version = 1")

        sqlite_storage.initialize_database()
        with sqlite_storage.connect() as connection:
            profit_factor_column = next(
                dict(row)
                for row in connection.execute("PRAGMA table_info(backtest_runs)")
                if row["name"] == "profit_factor"
            )
            foreign_key_targets = {
                row["table"] for row in connection.execute("PRAGMA foreign_key_list(backtest_trades)")
            }
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            run_count = connection.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0]

        self.assertEqual(profit_factor_column["notnull"], 0)
        self.assertEqual(foreign_key_targets, {"backtest_runs", "bots", "bot_versions"})
        self.assertEqual(user_version, 2)
        self.assertEqual(run_count, 1)


if __name__ == "__main__":
    unittest.main()
