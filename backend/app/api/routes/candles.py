from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.candle_service import get_candles

router = APIRouter(prefix="/api", tags=["candles"])


@router.get("/candles")
def candles(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="15m"),
    limit: int = Query(default=200, ge=50, le=1000),
) -> dict:
    try:
        return get_candles(symbol=symbol, interval=interval, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc