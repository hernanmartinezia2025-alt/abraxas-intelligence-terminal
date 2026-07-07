from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from backend.app.core.config import DB_PATH

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
"""

@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)
