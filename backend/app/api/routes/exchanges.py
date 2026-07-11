from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from backend.app.exchanges.ccxt_public import exchange_registry, fetch_candles, fetch_markets, fetch_order_book, fetch_ticker

router = APIRouter(prefix="/api/exchanges", tags=["exchange-public"])


def execute(callback):
    try:
        return callback()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("")
def exchanges() -> dict:
    return exchange_registry()


@router.get("/{exchange_id}/markets")
def markets(exchange_id: str = Path(min_length=2, max_length=30), limit: int = Query(default=100, ge=1, le=500)) -> dict:
    return execute(lambda: fetch_markets(exchange_id, limit))


@router.get("/{exchange_id}/ticker")
def ticker(exchange_id: str, symbol: str = Query(min_length=3, max_length=30)) -> dict:
    return execute(lambda: fetch_ticker(exchange_id, symbol))


@router.get("/{exchange_id}/order-book")
def order_book(exchange_id: str, symbol: str = Query(min_length=3, max_length=30), limit: int = Query(default=20, ge=5, le=100)) -> dict:
    return execute(lambda: fetch_order_book(exchange_id, symbol, limit))


@router.get("/{exchange_id}/candles")
def candles(exchange_id: str, symbol: str = Query(min_length=3, max_length=30), timeframe: str = Query(default="15m", pattern="^(1m|5m|15m|1h|4h|1d)$"), limit: int = Query(default=200, ge=10, le=1000)) -> dict:
    return execute(lambda: fetch_candles(exchange_id, symbol, timeframe, limit))
