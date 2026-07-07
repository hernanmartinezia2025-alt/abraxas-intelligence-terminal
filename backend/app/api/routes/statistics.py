from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.statistics_service import (
    get_monte_carlo,
    get_statistics,
    get_statistics_runs,
    get_statistics_summary,
)

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("")
def statistics(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="15m"),
    limit: int = Query(default=300, ge=80, le=1000),
    horizon_steps: int = Query(default=48, ge=6, le=240),
    paths: int = Query(default=700, ge=100, le=3000),
) -> dict:
    try:
        return get_statistics(
            symbol=symbol,
            interval=interval,
            limit=limit,
            horizon_steps=horizon_steps,
            paths=paths,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/summary")
def statistics_summary(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="15m"),
    limit: int = Query(default=300, ge=80, le=1000),
) -> dict:
    try:
        return get_statistics_summary(symbol=symbol, interval=interval, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/monte-carlo")
def monte_carlo(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="15m"),
    limit: int = Query(default=300, ge=80, le=1000),
    horizon_steps: int = Query(default=48, ge=6, le=240),
    paths: int = Query(default=700, ge=100, le=3000),
) -> dict:
    try:
        return get_monte_carlo(
            symbol=symbol,
            interval=interval,
            limit=limit,
            horizon_steps=horizon_steps,
            paths=paths,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/runs")
def statistics_runs(
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    run_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    try:
        return get_statistics_runs(symbol=symbol, timeframe=timeframe, run_type=run_type, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
