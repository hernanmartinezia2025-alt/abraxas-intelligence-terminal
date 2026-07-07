from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.feature_service import build_features_from_candles, list_features

router = APIRouter(prefix="/api/features", tags=["features"])


@router.get("")
def asset_features(
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    try:
        return list_features(symbol=symbol, timeframe=timeframe, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/build")
def build_features(
    symbol: str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="15m"),
    limit: int = Query(default=300, ge=40, le=1000),
) -> dict:
    try:
        return build_features_from_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
