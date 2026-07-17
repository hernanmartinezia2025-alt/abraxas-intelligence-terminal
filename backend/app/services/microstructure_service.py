from __future__ import annotations

from datetime import datetime, timezone

from backend.app.market.binance import fetch_aggregate_trades
from backend.app.market.local_order_book import DepthSequenceGap, LocalOrderBook
from backend.app.services.order_book_service import get_order_book
from backend.app.storage.microstructure import (
    get_microstructure_status,
    get_order_book_replay_anchor,
    list_order_book_deltas_for_replay,
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
    status = get_microstructure_status(symbol)
    stream_active = bool(status.get("continuous_stream"))
    return {
        "contract": "microstructure_storage_v1",
        **status,
        "boundaries": {
            "aggregate_trades": (
                "Persisted REST windows plus public WebSocket aggTrades."
                if stream_active
                else "Persisted REST windows; start the collector for continuous WebSocket flow."
            ),
            "order_book": (
                "Sequenced public L2 deltas plus periodic reconstructed-book snapshots."
                if stream_active
                else "Point-in-time snapshots only; continuous L2 collection is inactive."
            ),
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


def replay_order_book(
    symbol: str,
    target_time: int,
    levels: int = 100,
    max_deltas: int = 50_000,
) -> dict:
    normalized = symbol.upper().strip()
    target_time = int(target_time)
    status = get_microstructure_status(normalized)
    first_delta = status["order_book_deltas"].get("first_time")
    last_delta = status["order_book_deltas"].get("last_time")
    if first_delta is None or last_delta is None:
        raise ValueError("No persisted L2 delta coverage exists for this symbol.")
    if target_time < int(first_delta) or target_time > int(last_delta):
        raise ValueError(
            f"target_time must be inside persisted L2 coverage {first_delta}-{last_delta}."
        )

    target_iso = datetime.fromtimestamp(target_time / 1000, tz=timezone.utc).isoformat()
    anchor = get_order_book_replay_anchor(normalized, target_iso)
    if not anchor:
        raise ValueError("No reconstructed-book anchor exists at or before target_time.")
    deltas = list_order_book_deltas_for_replay(
        normalized,
        int(anchor["last_update_id"]),
        target_time,
        limit=max_deltas + 1,
    )
    if len(deltas) > max_deltas:
        raise ValueError(
            f"Replay requires more than max_deltas={max_deltas}; choose a nearer target or anchor."
        )

    book = LocalOrderBook.from_snapshot(anchor)
    applied = 0
    stale = 0
    try:
        for delta in deltas:
            if book.apply(delta):
                applied += 1
            else:
                stale += 1
    except DepthSequenceGap as exc:
        raise ValueError(f"Replay is incomplete because a persisted L2 sequence gap was found: {exc}") from exc

    reconstructed = book.snapshot_payload(limit=levels, fetched_at=target_iso)
    reconstructed["source"] = "sqlite_sequenced_l2_replay"
    return {
        "contract": "order_book_replay_v1",
        "symbol": normalized,
        "target_time": target_time,
        "coverage": {"first_event_time": first_delta, "last_event_time": last_delta},
        "anchor": {
            "snapshot_id": anchor["id"],
            "fetched_at": anchor["fetched_at"],
            "last_update_id": anchor["last_update_id"],
            "stored_levels": len(anchor["bids"]) + len(anchor["asks"]),
        },
        "replay": {
            "sequence_complete": True,
            "deltas_read": len(deltas),
            "deltas_applied": applied,
            "stale_deltas_skipped": stale,
            "final_update_id": book.last_update_id,
            "max_deltas": max_deltas,
        },
        "book": reconstructed,
        "claim_boundary": (
            "Sequence-complete reconstruction within the persisted anchor depth. "
            "It is not a full exchange book and does not expose hidden or cancelled stop orders."
        ),
        "execution_created": False,
    }
