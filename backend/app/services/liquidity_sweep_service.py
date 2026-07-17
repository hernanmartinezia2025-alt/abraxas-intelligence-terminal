from __future__ import annotations

from time import time

from backend.app.analytics.liquidity_sweep import build_liquidity_sweep_evaluation
from backend.app.market.binance import fetch_aggregate_trades
from backend.app.services.candle_service import get_candles
from backend.app.services.order_book_service import get_order_book
from backend.app.storage.liquidity_sweeps import list_liquidity_sweep_evaluations, save_liquidity_sweep_evaluation
from backend.app.storage.microstructure import (
    get_microstructure_status,
    list_aggregate_trades,
    save_aggregate_trades,
    save_order_book_snapshot,
)

ALLOWED_TIMEFRAMES = {"1m", "5m"}


def readiness() -> dict:
    return {
        "contract": "liquidity_sweep_observer_v2",
        "status": "observation_only",
        "allowed_timeframes": sorted(ALLOWED_TIMEFRAMES),
        "order_allowed": False,
        "available": ["closed_ohlcv", "closed_candle_volume", "squeeze_adx", "current_l2_snapshot", "closed_candle_aggregate_trade_flow", "persisted_l2_snapshots", "continuous_websocket_trade_flow", "continuous_l2_deltas", "audited_collector_lifecycle"],
        "missing": ["historical_l2_replay", "liquidation_clusters"],
        "unlock_rule": "Execution remains blocked until missing order-flow data, risk validation and paper evidence exist.",
    }


def evaluate_liquidity_sweep(
    symbol: str,
    timeframe: str,
    limit: int,
    account_equity: float,
    risk_pct: float,
) -> dict:
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError("SL Hunter v1 only accepts closed 1m or 5m candles.")
    candle_payload = get_candles(symbol=symbol.upper(), interval=timeframe, limit=limit)
    now_ms = int(time() * 1000)
    closed = [item for item in candle_payload["candles"] if int(item.get("close_time") or 0) <= now_ms]
    if len(closed) < 45:
        raise ValueError("Insufficient closed candles for liquidity sweep evaluation.")
    order_book = None
    order_book_error = None
    try:
        order_book = get_order_book(symbol=symbol.upper(), limit=100)
        save_order_book_snapshot(order_book)
    except Exception as exc:
        order_book_error = str(exc)
    trade_start = int(closed[-1]["timestamp"])
    trade_end = int(closed[-1]["close_time"])
    aggregate_trade_error = None
    trades_fetched = 0
    trades_saved = 0
    try:
        fetched_trades = fetch_aggregate_trades(
            symbol=symbol.upper(), start_time=trade_start, end_time=trade_end, limit=1000
        )
        trades_fetched = len(fetched_trades)
        trades_saved = save_aggregate_trades(fetched_trades)
    except Exception as exc:
        aggregate_trade_error = str(exc)
    aggregate_trades = list_aggregate_trades(
        symbol=symbol, start_time=trade_start, end_time=trade_end, limit=5000
    )
    microstructure_status = get_microstructure_status(symbol)
    result = build_liquidity_sweep_evaluation(
        candles=closed,
        order_book=order_book,
        aggregate_trades=aggregate_trades,
        microstructure_status=microstructure_status,
        symbol=symbol,
        timeframe=timeframe,
        account_equity=account_equity,
        risk_pct=risk_pct,
    )
    result["data_lineage"] = {
        "candles_served_from": candle_payload["served_from"],
        "closed_candles": len(closed),
        "latest_closed_at": closed[-1].get("close_time"),
        "order_book_error": order_book_error,
        "aggregate_trade_error": aggregate_trade_error,
        "aggregate_trades_fetched": trades_fetched,
        "aggregate_trades_saved": trades_saved,
        "microstructure_status": microstructure_status,
    }
    return save_liquidity_sweep_evaluation(result)


def history(limit: int = 20, symbol: str = "") -> dict:
    return list_liquidity_sweep_evaluations(limit=limit, symbol=symbol)
