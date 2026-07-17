from __future__ import annotations

from backend.app.market.binance import fetch_aggregate_trades
from backend.app.services.order_book_service import get_order_book
from backend.app.storage.microstructure import (
    get_microstructure_status,
    list_aggregate_trades,
    save_aggregate_trades,
    save_order_book_snapshot,
)


def capture_microstructure_window(
    symbol: str,
    start_time: int,
    end_time: int,
    depth_limit: int = 100,
) -> dict:
    if end_time <= start_time:
        raise ValueError("end_time must be greater than start_time.")
    if end_time - start_time > 3_600_000:
        raise ValueError("Public aggregate-trade capture windows are limited to one hour.")
    normalized = symbol.upper().strip()
    trades = fetch_aggregate_trades(
        symbol=normalized, start_time=start_time, end_time=end_time, limit=1000
    )
    saved_trades = save_aggregate_trades(trades)
    order_book = get_order_book(symbol=normalized, limit=depth_limit)
    snapshot = save_order_book_snapshot(order_book)
    persisted = list_aggregate_trades(normalized, start_time, end_time, limit=5000)
    return {
        "contract": "microstructure_capture_v1",
        "symbol": normalized,
        "window": {"start_time": start_time, "end_time": end_time},
        "aggregate_trades": {
            "fetched": len(trades),
            "saved": saved_trades,
            "persisted_in_window": len(persisted),
            "possibly_truncated": len(trades) == 1000,
        },
        "order_book": snapshot,
        "status": get_microstructure_status(normalized),
        "execution_created": False,
    }


def microstructure_status(symbol: str) -> dict:
    return {
        "contract": "microstructure_storage_v1",
        **get_microstructure_status(symbol),
        "boundaries": {
            "aggregate_trades": "REST windows, not a continuous WebSocket stream.",
            "order_book": "Persisted point-in-time snapshots, not continuous L2 deltas.",
            "liquidations": "Unavailable.",
        },
    }


def microstructure_trades(symbol: str, start_time: int, end_time: int, limit: int) -> dict:
    trades = list_aggregate_trades(symbol, start_time, end_time, limit=limit)
    return {
        "symbol": symbol.upper(),
        "start_time": start_time,
        "end_time": end_time,
        "count": len(trades),
        "trades": trades,
    }
