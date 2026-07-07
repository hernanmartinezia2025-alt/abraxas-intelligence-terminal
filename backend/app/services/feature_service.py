from __future__ import annotations

from backend.app.analytics.features import build_asset_features
from backend.app.storage.candles import list_candles
from backend.app.storage.features import latest_asset_features, save_asset_features


def build_features_from_candles(symbol: str, timeframe: str, limit: int = 300) -> dict:
    candles = list_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    features = build_asset_features(symbol=symbol, timeframe=timeframe, candles=candles)
    saved = save_asset_features(features)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candles_used": len(candles),
        "features_generated": len(features),
        "features_saved": saved,
        "latest": latest_asset_features(symbol=symbol, timeframe=timeframe, limit=1),
    }


def list_features(symbol: str | None = None, timeframe: str | None = None, limit: int = 100) -> dict:
    return {
        "symbol": symbol.upper() if symbol else None,
        "timeframe": timeframe,
        "limit": limit,
        "features": latest_asset_features(symbol=symbol, timeframe=timeframe, limit=limit),
    }
