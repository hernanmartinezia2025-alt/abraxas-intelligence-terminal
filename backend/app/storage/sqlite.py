from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from backend.app.core.config import DB_PATH

LOGGER = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    change_24h REAL NOT NULL,
    volume_24h REAL NOT NULL,
    fear_greed_value INTEGER NOT NULL,
    fear_greed_label TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    abraxas_reading TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol_time
ON market_snapshots(symbol, timestamp);

CREATE TABLE IF NOT EXISTS macro_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(series_id, observation_date)
);

CREATE INDEX IF NOT EXISTS idx_macro_observations_category_date
ON macro_observations(category, observation_date);

CREATE TABLE IF NOT EXISTS market_candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time INTEGER NOT NULL,
    close_time INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    quote_volume REAL NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(symbol, timeframe, open_time)
);

CREATE INDEX IF NOT EXISTS idx_market_candles_symbol_time
ON market_candles(symbol, timeframe, open_time);

CREATE INDEX IF NOT EXISTS idx_market_candles_open_time
ON market_candles(open_time);

CREATE TABLE IF NOT EXISTS asset_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    return_1 REAL NOT NULL,
    return_5 REAL NOT NULL,
    return_20 REAL NOT NULL,
    volatility REAL NOT NULL,
    z_score REAL NOT NULL,
    drawdown REAL NOT NULL,
    trend_strength REAL NOT NULL,
    volume_change REAL NOT NULL,
    risk_score REAL NOT NULL,
    regime_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_asset_features_symbol_time
ON asset_features(symbol, timeframe, timestamp);

CREATE INDEX IF NOT EXISTS idx_asset_features_regime
ON asset_features(regime_label, timestamp);

CREATE TABLE IF NOT EXISTS statistics_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    run_type TEXT NOT NULL,
    input_start INTEGER,
    input_end INTEGER,
    metrics_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_statistics_runs_symbol_time
ON statistics_runs(symbol, timeframe, created_at);

CREATE INDEX IF NOT EXISTS idx_statistics_runs_type_time
ON statistics_runs(run_type, created_at);

CREATE TABLE IF NOT EXISTS regime_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    regime_label TEXT NOT NULL,
    confidence REAL NOT NULL,
    risk_score REAL NOT NULL,
    market_bias TEXT NOT NULL,
    volatility_state TEXT NOT NULL,
    trend_state TEXT NOT NULL,
    drawdown_state TEXT NOT NULL,
    feature_count INTEGER NOT NULL,
    reasons_json TEXT NOT NULL,
    reading TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_regime_snapshots_symbol_time
ON regime_snapshots(symbol, timeframe, timestamp);

CREATE INDEX IF NOT EXISTS idx_regime_snapshots_label_time
ON regime_snapshots(regime_label, timestamp);

CREATE TABLE IF NOT EXISTS live_events (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    lat REAL,
    lon REAL,
    country TEXT,
    url TEXT,
    severity TEXT NOT NULL,
    published_at TEXT NOT NULL,
    freshness_minutes INTEGER NOT NULL,
    related_assets TEXT NOT NULL,
    vector_tags TEXT NOT NULL,
    raw_url TEXT,
    fetched_at TEXT NOT NULL,
    raw_payload TEXT,
    UNIQUE(source, id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_live_events_source_url
ON live_events(source, url)
WHERE url IS NOT NULL AND url != '';

CREATE INDEX IF NOT EXISTS idx_live_events_type_time
ON live_events(type, published_at);

CREATE INDEX IF NOT EXISTS idx_live_events_severity_time
ON live_events(severity, published_at);

CREATE TABLE IF NOT EXISTS live_source_health (
    source TEXT PRIMARY KEY,
    ok INTEGER NOT NULL,
    last_success_at TEXT,
    latency_ms INTEGER NOT NULL,
    event_count INTEGER NOT NULL,
    error TEXT,
    max_stale_minutes INTEGER NOT NULL,
    checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    base_symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    risk_profile TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bots_status
ON bots(status, updated_at);

CREATE TABLE IF NOT EXISTS bot_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    strategy_json TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
    UNIQUE(bot_id, version)
);

CREATE INDEX IF NOT EXISTS idx_bot_versions_bot
ON bot_versions(bot_id, version);

CREATE TABLE IF NOT EXISTS backtest_runs (
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
    profit_factor REAL,
    metrics_json TEXT NOT NULL,
    trades_json TEXT NOT NULL,
    equity_curve_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
    FOREIGN KEY(bot_version_id) REFERENCES bot_versions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_bot_time
ON backtest_runs(bot_id, created_at);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_symbol_time
ON backtest_runs(symbol, timeframe, created_at);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    bot_id INTEGER NOT NULL,
    bot_version_id INTEGER NOT NULL,
    trade_index INTEGER NOT NULL,
    side TEXT NOT NULL DEFAULT 'long',
    entry_signal_timestamp INTEGER,
    exit_signal_timestamp INTEGER,
    entry_timestamp INTEGER NOT NULL,
    exit_timestamp INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    quantity REAL NOT NULL,
    allocated_equity REAL,
    gross_pnl REAL,
    entry_fee REAL,
    exit_fee REAL,
    fees_paid REAL,
    slippage_cost REAL,
    pnl REAL NOT NULL,
    return_pct REAL NOT NULL,
    bars_held INTEGER,
    exit_reason TEXT,
    forced_exit INTEGER NOT NULL DEFAULT 0 CHECK(forced_exit IN (0, 1)),
    created_at TEXT NOT NULL,
    FOREIGN KEY(backtest_id) REFERENCES backtest_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
    FOREIGN KEY(bot_version_id) REFERENCES bot_versions(id) ON DELETE CASCADE,
    UNIQUE(backtest_id, trade_index)
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_exit
ON backtest_trades(backtest_id, exit_timestamp);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_bot_version
ON backtest_trades(bot_id, bot_version_id, exit_timestamp);

CREATE TABLE IF NOT EXISTS backtest_equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    bot_id INTEGER NOT NULL,
    bot_version_id INTEGER NOT NULL,
    point_index INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    equity REAL NOT NULL,
    benchmark_equity REAL,
    close REAL NOT NULL,
    drawdown_pct REAL,
    in_position INTEGER NOT NULL CHECK(in_position IN (0, 1)),
    created_at TEXT NOT NULL,
    FOREIGN KEY(backtest_id) REFERENCES backtest_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
    FOREIGN KEY(bot_version_id) REFERENCES bot_versions(id) ON DELETE CASCADE,
    UNIQUE(backtest_id, point_index)
);

CREATE INDEX IF NOT EXISTS idx_backtest_equity_run_time
ON backtest_equity(backtest_id, timestamp, point_index);

CREATE INDEX IF NOT EXISTS idx_backtest_equity_bot_version
ON backtest_equity(bot_id, bot_version_id, timestamp);

CREATE TABLE IF NOT EXISTS risk_limits (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    max_position_pct REAL NOT NULL CHECK (max_position_pct > 0 AND max_position_pct <= 100),
    max_daily_loss_pct REAL NOT NULL CHECK (max_daily_loss_pct > 0 AND max_daily_loss_pct <= 100),
    max_drawdown_pct REAL NOT NULL CHECK (max_drawdown_pct > 0 AND max_drawdown_pct <= 100),
    cooldown_minutes INTEGER NOT NULL CHECK (cooldown_minutes >= 0),
    symbol_whitelist TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    kill_switch_active INTEGER NOT NULL CHECK (kill_switch_active IN (0, 1)),
    reason TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_audit_log_created
ON risk_audit_log(created_at);

CREATE TABLE IF NOT EXISTS risk_validation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    approved INTEGER NOT NULL CHECK (approved IN (0, 1)),
    request_json TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_validation_symbol_created
ON risk_validation_log(symbol, created_at);

CREATE TABLE IF NOT EXISTS simulated_accounts (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    initial_balance REAL NOT NULL,
    cash_balance REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    peak_equity REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulated_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    bot_id INTEGER,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity REAL NOT NULL,
    status TEXT NOT NULL,
    reference_price REAL NOT NULL,
    fill_price REAL,
    fee REAL,
    risk_validation_id INTEGER NOT NULL,
    rejection_reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES simulated_accounts(id),
    FOREIGN KEY(bot_id) REFERENCES bots(id),
    FOREIGN KEY(risk_validation_id) REFERENCES risk_validation_log(id)
);

CREATE TABLE IF NOT EXISTS simulated_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    average_price REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, symbol),
    FOREIGN KEY(account_id) REFERENCES simulated_accounts(id)
);

CREATE TABLE IF NOT EXISTS simulated_fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL,
    filled_at TEXT NOT NULL,
    FOREIGN KEY(order_id) REFERENCES simulated_orders(id),
    FOREIGN KEY(account_id) REFERENCES simulated_accounts(id)
);

CREATE TABLE IF NOT EXISTS simulated_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    reference_id INTEGER,
    symbol TEXT,
    cash_delta REAL NOT NULL,
    realized_pnl_delta REAL NOT NULL,
    cash_balance REAL NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES simulated_accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_simulated_orders_created ON simulated_orders(created_at);
CREATE INDEX IF NOT EXISTS idx_simulated_fills_filled ON simulated_fills(filled_at);
CREATE INDEX IF NOT EXISTS idx_simulated_ledger_created ON simulated_ledger(created_at);

CREATE TABLE IF NOT EXISTS exchange_source_health (
    exchange_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    ok INTEGER NOT NULL CHECK (ok IN (0, 1)),
    latency_ms INTEGER NOT NULL,
    error TEXT,
    checked_at TEXT NOT NULL,
    PRIMARY KEY(exchange_id, endpoint)
);

CREATE TABLE IF NOT EXISTS execution_intents (
    id TEXT PRIMARY KEY,
    environment TEXT NOT NULL CHECK (environment IN ('backtest', 'paper', 'live')),
    adapter TEXT NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
    order_type TEXT NOT NULL CHECK (order_type IN ('market', 'limit')),
    quantity REAL NOT NULL,
    limit_price REAL,
    bot_id INTEGER,
    status TEXT NOT NULL,
    result_reference TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(bot_id) REFERENCES bots(id)
);

CREATE INDEX IF NOT EXISTS idx_execution_intents_environment_created
ON execution_intents(environment, created_at);
"""

BACKTEST_INTEGRITY_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_backtest_runs_version_bot_insert
BEFORE INSERT ON backtest_runs
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM bot_versions
    WHERE id = NEW.bot_version_id AND bot_id = NEW.bot_id
)
BEGIN
    SELECT RAISE(ABORT, 'backtest version does not belong to bot');
END;

CREATE TRIGGER IF NOT EXISTS trg_backtest_runs_version_bot_update
BEFORE UPDATE OF bot_id, bot_version_id ON backtest_runs
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM bot_versions
    WHERE id = NEW.bot_version_id AND bot_id = NEW.bot_id
)
BEGIN
    SELECT RAISE(ABORT, 'backtest version does not belong to bot');
END;

CREATE TRIGGER IF NOT EXISTS trg_backtest_trades_parent_insert
BEFORE INSERT ON backtest_trades
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM backtest_runs
    WHERE id = NEW.backtest_id
      AND bot_id = NEW.bot_id
      AND bot_version_id = NEW.bot_version_id
)
BEGIN
    SELECT RAISE(ABORT, 'backtest trade does not match parent run');
END;

CREATE TRIGGER IF NOT EXISTS trg_backtest_trades_parent_update
BEFORE UPDATE OF backtest_id, bot_id, bot_version_id ON backtest_trades
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM backtest_runs
    WHERE id = NEW.backtest_id
      AND bot_id = NEW.bot_id
      AND bot_version_id = NEW.bot_version_id
)
BEGIN
    SELECT RAISE(ABORT, 'backtest trade does not match parent run');
END;

CREATE TRIGGER IF NOT EXISTS trg_backtest_equity_parent_insert
BEFORE INSERT ON backtest_equity
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM backtest_runs
    WHERE id = NEW.backtest_id
      AND bot_id = NEW.bot_id
      AND bot_version_id = NEW.bot_version_id
)
BEGIN
    SELECT RAISE(ABORT, 'backtest equity does not match parent run');
END;

CREATE TRIGGER IF NOT EXISTS trg_backtest_equity_parent_update
BEFORE UPDATE OF backtest_id, bot_id, bot_version_id ON backtest_equity
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM backtest_runs
    WHERE id = NEW.backtest_id
      AND bot_id = NEW.bot_id
      AND bot_version_id = NEW.bot_version_id
)
BEGIN
    SELECT RAISE(ABORT, 'backtest equity does not match parent run');
END;
"""

BACKTEST_SCHEMA_VERSION = 2

@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _parse_legacy_list(value: object, run_id: int, field: str) -> list[dict]:
    try:
        parsed = json.loads(str(value)) if value else []
    except (json.JSONDecodeError, TypeError, ValueError):
        LOGGER.warning("Skipping corrupt %s for legacy backtest run %s", field, run_id)
        return []
    if not isinstance(parsed, list):
        LOGGER.warning("Skipping non-list %s for legacy backtest run %s", field, run_id)
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _migrate_nullable_profit_factor(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]: row
        for row in connection.execute("PRAGMA table_info(backtest_runs)").fetchall()
    }
    profit_factor_column = columns.get("profit_factor")
    if not profit_factor_column or not int(profit_factor_column["notnull"]):
        return

    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("PRAGMA legacy_alter_table = ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("ALTER TABLE backtest_runs RENAME TO backtest_runs_v1")
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
                profit_factor REAL,
                metrics_json TEXT NOT NULL,
                trades_json TEXT NOT NULL,
                equity_curve_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(bot_id) REFERENCES bots(id) ON DELETE CASCADE,
                FOREIGN KEY(bot_version_id) REFERENCES bot_versions(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            INSERT INTO backtest_runs (
                id, bot_id, bot_version_id, symbol, timeframe, input_start, input_end,
                initial_equity, final_equity, roi_pct, max_drawdown_pct, total_trades,
                win_rate_pct, profit_factor, metrics_json, trades_json,
                equity_curve_json, created_at
            )
            SELECT
                id, bot_id, bot_version_id, symbol, timeframe, input_start, input_end,
                initial_equity, final_equity, roi_pct, max_drawdown_pct, total_trades,
                win_rate_pct, profit_factor, metrics_json, trades_json,
                equity_curve_json, created_at
            FROM backtest_runs_v1
            """
        )
        connection.execute("DROP TABLE backtest_runs_v1")
        connection.execute(
            "CREATE INDEX idx_backtest_runs_bot_time ON backtest_runs(bot_id, created_at)"
        )
        connection.execute(
            "CREATE INDEX idx_backtest_runs_symbol_time ON backtest_runs(symbol, timeframe, created_at)"
        )
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA legacy_alter_table = OFF")
        connection.execute("PRAGMA foreign_keys = ON")


def _backfill_backtest_payloads(connection: sqlite3.Connection) -> None:
    runs = connection.execute(
        """
        SELECT id, bot_id, bot_version_id, trades_json, equity_curve_json, created_at
        FROM backtest_runs
        ORDER BY id
        """
    ).fetchall()
    for run in runs:
        trades = _parse_legacy_list(run["trades_json"], int(run["id"]), "trades_json")
        equity_curve = _parse_legacy_list(run["equity_curve_json"], int(run["id"]), "equity_curve_json")
        trade_rows = []
        for trade_index, trade in enumerate(trades, start=1):
            try:
                forced_exit = bool(trade.get("forced_exit"))
                trade_rows.append(
                    {
                        "backtest_id": int(run["id"]),
                        "bot_id": int(run["bot_id"]),
                        "bot_version_id": int(run["bot_version_id"]),
                        "trade_index": trade_index,
                        "side": str(trade.get("side") or "long"),
                        "entry_timestamp": int(trade["entry_timestamp"]),
                        "exit_timestamp": int(trade["exit_timestamp"]),
                        "entry_price": float(trade["entry_price"]),
                        "exit_price": float(trade["exit_price"]),
                        "quantity": float(trade["quantity"]),
                        "pnl": float(trade.get("pnl") or 0),
                        "return_pct": float(trade.get("return_pct") or 0),
                        "exit_reason": str(
                            trade.get("exit_reason") or ("end_of_data" if forced_exit else "legacy")
                        ),
                        "forced_exit": int(forced_exit),
                        "created_at": run["created_at"],
                    }
                )
            except (KeyError, TypeError, ValueError):
                LOGGER.warning(
                    "Skipping invalid trade %s for legacy backtest run %s",
                    trade_index,
                    run["id"],
                )
        if trade_rows:
            connection.executemany(
                """
                INSERT OR IGNORE INTO backtest_trades (
                    backtest_id, bot_id, bot_version_id, trade_index, side,
                    entry_timestamp, exit_timestamp, entry_price, exit_price,
                    quantity, pnl, return_pct, exit_reason, forced_exit, created_at
                ) VALUES (
                    :backtest_id, :bot_id, :bot_version_id, :trade_index, :side,
                    :entry_timestamp, :exit_timestamp, :entry_price, :exit_price,
                    :quantity, :pnl, :return_pct, :exit_reason, :forced_exit, :created_at
                )
                """,
                trade_rows,
            )

        equity_rows = []
        for point_index, point in enumerate(equity_curve, start=1):
            try:
                equity_rows.append(
                    {
                        "backtest_id": int(run["id"]),
                        "bot_id": int(run["bot_id"]),
                        "bot_version_id": int(run["bot_version_id"]),
                        "point_index": point_index,
                        "timestamp": int(point["timestamp"]),
                        "equity": float(point["equity"]),
                        "benchmark_equity": point.get("benchmark_equity"),
                        "close": float(point["close"]),
                        "drawdown_pct": point.get("drawdown_pct"),
                        "in_position": int(bool(point.get("in_position"))),
                        "created_at": run["created_at"],
                    }
                )
            except (KeyError, TypeError, ValueError):
                LOGGER.warning(
                    "Skipping invalid equity point %s for legacy backtest run %s",
                    point_index,
                    run["id"],
                )
        if equity_rows:
            connection.executemany(
                """
                INSERT OR IGNORE INTO backtest_equity (
                    backtest_id, bot_id, bot_version_id, point_index, timestamp,
                    equity, benchmark_equity, close, drawdown_pct, in_position, created_at
                ) VALUES (
                    :backtest_id, :bot_id, :bot_version_id, :point_index, :timestamp,
                    :equity, :benchmark_equity, :close, :drawdown_pct, :in_position, :created_at
                )
                """,
                equity_rows,
            )


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if user_version < 1:
            _backfill_backtest_payloads(connection)
        if user_version < 2:
            _migrate_nullable_profit_factor(connection)
        connection.executescript(BACKTEST_INTEGRITY_TRIGGERS)
        if user_version < BACKTEST_SCHEMA_VERSION:
            connection.execute(f"PRAGMA user_version = {BACKTEST_SCHEMA_VERSION}")
