from __future__ import annotations

from typing import Iterable

import requests

from backend.app.core.config import REQUEST_TIMEOUT

TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
KLINES_URL = "https://api.binance.com/api/v3/klines"


def fetch_24h_tickers(symbols: Iterable[str]) -> list[dict]:
    rows = []
    for symbol in symbols:
        response = requests.get(TICKER_URL, params={"symbol": symbol}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        rows.append(
            {
                "symbol": payload["symbol"],
                "price": float(payload["lastPrice"]),
                "change_24h": float(payload["priceChangePercent"]),
                "volume_24h": float(payload["quoteVolume"]),
            }
        )
    return rows


def fetch_klines(symbol: str, interval: str = "15m", limit: int = 200) -> list[dict]:
    response = requests.get(
        KLINES_URL,
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    candles = []
    for row in response.json():
        candles.append(
            {
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "close_time": int(row[6]),
                "quote_volume": float(row[7]),
            }
        )
    return candles
