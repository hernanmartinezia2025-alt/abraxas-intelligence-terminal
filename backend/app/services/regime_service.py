from __future__ import annotations

from backend.app.analytics.regimes import analyze_regime
from backend.app.services.candle_service import get_candles
from backend.app.services.feature_service import build_features_from_candles
from backend.app.storage.features import latest_asset_features
from backend.app.storage.regimes import list_regime_snapshots, save_regime_snapshot


def get_regime(symbol: str, timeframe: str, limit: int = 120, refresh: bool = False) -> dict:
    selected_symbol = symbol.upper()
    if refresh:
        get_candles(symbol=selected_symbol, interval=timeframe, limit=max(limit, 120))
        build_features_from_candles(symbol=selected_symbol, timeframe=timeframe, limit=max(limit, 120))

    features = latest_asset_features(symbol=selected_symbol, timeframe=timeframe, limit=limit)
    if len(features) < 30:
        get_candles(symbol=selected_symbol, interval=timeframe, limit=max(limit, 120))
        build_features_from_candles(symbol=selected_symbol, timeframe=timeframe, limit=max(limit, 120))
        features = latest_asset_features(symbol=selected_symbol, timeframe=timeframe, limit=limit)

    snapshot = analyze_regime(symbol=selected_symbol, timeframe=timeframe, features=features)
    snapshot_id = save_regime_snapshot(snapshot)
    return {**snapshot, "regime_snapshot_id": snapshot_id}


def get_regime_snapshots(symbol: str | None = None, timeframe: str | None = None, limit: int = 100) -> dict:
    return {
        "symbol": symbol.upper() if symbol else None,
        "timeframe": timeframe,
        "limit": limit,
        "snapshots": list_regime_snapshots(symbol=symbol, timeframe=timeframe, limit=limit),
    }
