from __future__ import annotations

from backend.app.market.binance import fetch_klines
from backend.app.storage.candles import list_candles, save_candles
from backend.app.services.feature_service import build_features_from_candles


def get_candles(symbol: str, interval: str, limit: int) -> dict:
    source = "binance"
    features_saved = 0
    try:
        candles = fetch_klines(symbol=symbol, interval=interval, limit=limit)
        saved = save_candles(symbol=symbol, timeframe=interval, candles=candles, source=source)
        feature_result = build_features_from_candles(symbol=symbol, timeframe=interval, limit=max(limit, 80))
        features_saved = feature_result["features_saved"]
        served_from = "live_and_cached"
    except Exception:
        candles = list_candles(symbol=symbol, timeframe=interval, limit=limit)
        saved = 0
        served_from = "sqlite_cache"
        if not candles:
            raise

    return {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
        "source": source,
        "served_from": served_from,
        "saved": saved,
        "features_saved": features_saved,
        "candles": candles,
    }
