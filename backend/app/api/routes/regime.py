from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.regime_service import get_regime, get_regime_snapshots

router = APIRouter(prefix="/api/regime", tags=["regime"])


@router.get("")
def regime(
    symbol: str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="15m"),
    limit: int = Query(default=120, ge=30, le=1000),
    refresh: bool = Query(default=False),
) -> dict:
    try:
        return get_regime(symbol=symbol, timeframe=timeframe, limit=limit, refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/snapshots")
def regime_snapshots(
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    try:
        return get_regime_snapshots(symbol=symbol, timeframe=timeframe, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
