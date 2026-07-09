from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import requests

from backend.app.core.config import REQUEST_TIMEOUT

TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
KLINES_URL = "https://api.binance.com/api/v3/klines"
DEPTH_URL = "https://api.binance.com/api/v3/depth"


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


def fetch_order_book(symbol: str, limit: int = 20) -> dict:
    normalized_symbol = symbol.upper().strip()
    response = requests.get(
        DEPTH_URL,
        params={"symbol": normalized_symbol, "limit": limit},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()

    def normalize_levels(levels: list[list[str]]) -> list[dict]:
        normalized = []
        for price, quantity in levels:
            price_value = float(price)
            quantity_value = float(quantity)
            normalized.append(
                {
                    "price": price_value,
                    "quantity": quantity_value,
                    "notional": price_value * quantity_value,
                }
            )
        return normalized

    bids = normalize_levels(payload.get("bids", []))
    asks = normalize_levels(payload.get("asks", []))
    best_bid = bids[0]["price"] if bids else None
    best_ask = asks[0]["price"] if asks else None
    spread = (best_ask - best_bid) if best_bid is not None and best_ask is not None else None
    mid_price = ((best_ask + best_bid) / 2) if spread is not None else None
    spread_percent = (spread / mid_price * 100) if spread is not None and mid_price else None

    return {
        "symbol": normalized_symbol,
        "source": "binance",
        "market_type": "spot",
        "last_update_id": payload.get("lastUpdateId"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "limit": limit,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "spread_percent": spread_percent,
        "mid_price": mid_price,
        "bids": bids,
        "asks": asks,
    }
