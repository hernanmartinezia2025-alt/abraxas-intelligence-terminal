from __future__ import annotations

from backend.app.market.binance import fetch_order_book

ALLOWED_DEPTH_LIMITS = [5, 10, 20, 50, 100]


def normalize_depth_limit(limit: int) -> int:
    for allowed in ALLOWED_DEPTH_LIMITS:
        if limit <= allowed:
            return allowed
    return ALLOWED_DEPTH_LIMITS[-1]


def get_order_book(symbol: str = "BTCUSDT", limit: int = 20) -> dict:
    depth_limit = normalize_depth_limit(limit)
    return fetch_order_book(symbol=symbol, limit=depth_limit)
