from __future__ import annotations

from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_candles(symbol: str, timeframe: str, candles: list[dict], source: str = "binance") -> int:
    initialize_database()
    if not candles:
        return 0

    created_at = utc_now_iso()
    rows = []
    for candle in candles:
        open_time = int(candle["timestamp"])
        rows.append(
            {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "open_time": open_time,
                "close_time": int(candle.get("close_time") or open_time),
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle["volume"]),
                "quote_volume": float(candle.get("quote_volume") or 0),
                "source": source,
                "created_at": created_at,
            }
        )

    with connect() as connection:
        connection.executemany(
            """
            INSERT INTO market_candles (
                symbol, timeframe, open_time, close_time, open, high, low, close,
                volume, quote_volume, source, created_at
            ) VALUES (
                :symbol, :timeframe, :open_time, :close_time, :open, :high, :low, :close,
                :volume, :quote_volume, :source, :created_at
            )
            ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
                close_time = excluded.close_time,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                quote_volume = excluded.quote_volume,
                source = excluded.source,
                created_at = excluded.created_at
            """,
            rows,
        )
    return len(rows)


def list_candles(symbol: str, timeframe: str, limit: int = 200) -> list[dict]:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT open_time, close_time, open, high, low, close, volume, quote_volume
            FROM market_candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY open_time DESC
            LIMIT ?
            """,
            (symbol.upper(), timeframe, limit),
        ).fetchall()

    candles = []
    for row in reversed(rows):
        candles.append(
            {
                "timestamp": int(row["open_time"]),
                "close_time": int(row["close_time"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "quote_volume": float(row["quote_volume"]),
            }
        )
    return candles
