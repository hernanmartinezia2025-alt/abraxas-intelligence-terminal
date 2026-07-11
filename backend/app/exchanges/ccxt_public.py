from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

import ccxt

from backend.app.storage.sqlite import connect, initialize_database

ALLOWED_EXCHANGES = {
    "binance": {"label": "Binance", "default_symbol": "BTC/USDT"},
    "bingx": {"label": "BingX", "default_symbol": "BTC/USDT"},
    "bybit": {"label": "Bybit", "default_symbol": "BTC/USDT"},
    "kraken": {"label": "Kraken", "default_symbol": "BTC/USD"},
    "coinbase": {"label": "Coinbase", "default_symbol": "BTC/USD"},
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def exchange_registry() -> dict:
    return {
        "mode": "public_read_only",
        "private_api": "blocked",
        "exchanges": [
            {"id": exchange_id, **metadata, "capabilities": ["markets", "ticker", "order_book", "ohlcv"]}
            for exchange_id, metadata in ALLOWED_EXCHANGES.items()
        ],
    }


def _exchange(exchange_id: str):
    normalized = exchange_id.strip().lower()
    if normalized not in ALLOWED_EXCHANGES:
        raise ValueError(f"Exchange not allowed: {exchange_id}")
    exchange_class = getattr(ccxt, normalized)
    return exchange_class({"enableRateLimit": True, "timeout": 12_000}), normalized


def _record_health(exchange_id: str, endpoint: str, ok: bool, started: float, error: str | None = None) -> None:
    initialize_database()
    latency_ms = max(0, int((perf_counter() - started) * 1000))
    with connect() as connection:
        connection.execute(
            """INSERT INTO exchange_source_health (exchange_id, endpoint, ok, latency_ms, error, checked_at)
            VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(exchange_id, endpoint) DO UPDATE SET
            ok=excluded.ok, latency_ms=excluded.latency_ms, error=excluded.error, checked_at=excluded.checked_at""",
            (exchange_id, endpoint, int(ok), latency_ms, error, utc_now_iso()),
        )


def _public_call(exchange_id: str, endpoint: str, callback):
    started = perf_counter()
    normalized = exchange_id.strip().lower()
    try:
        exchange, normalized = _exchange(exchange_id)
        result = callback(exchange)
        _record_health(normalized, endpoint, True, started)
        return result
    except Exception as exc:
        if normalized in ALLOWED_EXCHANGES:
            _record_health(normalized, endpoint, False, started, str(exc)[:1000])
        raise


def fetch_markets(exchange_id: str, limit: int = 100) -> dict:
    def call(exchange):
        markets = exchange.load_markets()
        rows = []
        for symbol, market in markets.items():
            if not market.get("active", True) or not market.get("spot", False):
                continue
            rows.append({"symbol": symbol, "base": market.get("base"), "quote": market.get("quote"), "active": market.get("active"), "spot": market.get("spot")})
            if len(rows) >= limit:
                break
        return {"exchange": exchange.id, "count": len(rows), "markets": rows, "fetched_at": utc_now_iso()}
    return _public_call(exchange_id, "markets", call)


def fetch_ticker(exchange_id: str, symbol: str) -> dict:
    def call(exchange):
        ticker = exchange.fetch_ticker(symbol)
        return {"exchange": exchange.id, "symbol": ticker.get("symbol") or symbol, "timestamp": ticker.get("timestamp"), "last": ticker.get("last"), "bid": ticker.get("bid"), "ask": ticker.get("ask"), "open": ticker.get("open"), "high": ticker.get("high"), "low": ticker.get("low"), "change": ticker.get("change"), "percentage": ticker.get("percentage"), "base_volume": ticker.get("baseVolume"), "quote_volume": ticker.get("quoteVolume"), "fetched_at": utc_now_iso()}
    return _public_call(exchange_id, "ticker", call)


def fetch_order_book(exchange_id: str, symbol: str, limit: int = 20) -> dict:
    def call(exchange):
        book = exchange.fetch_order_book(symbol, limit)
        return {"exchange": exchange.id, "symbol": book.get("symbol") or symbol, "timestamp": book.get("timestamp"), "bids": book.get("bids", [])[:limit], "asks": book.get("asks", [])[:limit], "fetched_at": utc_now_iso()}
    return _public_call(exchange_id, "order_book", call)


def fetch_candles(exchange_id: str, symbol: str, timeframe: str = "15m", limit: int = 200) -> dict:
    def call(exchange):
        rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        candles = [{"timestamp": row[0], "open": row[1], "high": row[2], "low": row[3], "close": row[4], "volume": row[5]} for row in rows]
        return {"exchange": exchange.id, "symbol": symbol, "timeframe": timeframe, "count": len(candles), "candles": candles, "fetched_at": utc_now_iso()}
    return _public_call(exchange_id, "ohlcv", call)
