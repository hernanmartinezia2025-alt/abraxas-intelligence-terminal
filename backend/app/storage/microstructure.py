from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def save_aggregate_trades(trades: list[dict]) -> int:
    initialize_database()
    if not trades:
        return 0
    with connect() as connection:
        before = connection.total_changes
        connection.executemany(
            """
            INSERT INTO market_aggregate_trades (
                symbol, aggregate_trade_id, first_trade_id, last_trade_id,
                event_time, price, quantity, quote_quantity, buyer_is_maker,
                aggressor_side, source, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, aggregate_trade_id) DO NOTHING
            """,
            [
                (
                    item["symbol"], item["aggregate_trade_id"], item["first_trade_id"],
                    item["last_trade_id"], item["event_time"], item["price"],
                    item["quantity"], item["quote_quantity"], int(item["buyer_is_maker"]),
                    item["aggressor_side"], item["source"], item["fetched_at"],
                )
                for item in trades
            ],
        )
        return connection.total_changes - before


def list_aggregate_trades(symbol: str, start_time: int, end_time: int, limit: int = 5000) -> list[dict]:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT aggregate_trade_id, first_trade_id, last_trade_id, event_time,
                   price, quantity, quote_quantity, buyer_is_maker, aggressor_side,
                   source, fetched_at
            FROM market_aggregate_trades
            WHERE symbol = ? AND event_time BETWEEN ? AND ?
            ORDER BY event_time, aggregate_trade_id
            LIMIT ?
            """,
            (symbol.upper(), int(start_time), int(end_time), int(limit)),
        ).fetchall()
    return [
        {
            **dict(row),
            "buyer_is_maker": bool(row["buyer_is_maker"]),
            "symbol": symbol.upper(),
        }
        for row in rows
    ]


def save_order_book_snapshot(order_book: dict) -> dict:
    initialize_database()
    bids = order_book.get("bids") or []
    asks = order_book.get("asks") or []
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO order_book_snapshots (
                symbol, source, last_update_id, best_bid, best_ask, spread,
                spread_percent, mid_price, level_count, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_book["symbol"], order_book.get("source", "binance"),
                order_book.get("last_update_id"), order_book.get("best_bid"),
                order_book.get("best_ask"), order_book.get("spread"),
                order_book.get("spread_percent"), order_book.get("mid_price"),
                len(bids) + len(asks), order_book["fetched_at"],
            ),
        )
        snapshot_id = int(cursor.lastrowid)
        levels = []
        for side, rows in (("bid", bids), ("ask", asks)):
            for index, item in enumerate(rows):
                levels.append(
                    (
                        snapshot_id, order_book["symbol"], side, index,
                        float(item["price"]), float(item["quantity"]), float(item["notional"]),
                    )
                )
        connection.executemany(
            """
            INSERT INTO order_book_levels (
                snapshot_id, symbol, side, level_index, price, quantity, notional
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            levels,
        )
    return {"snapshot_id": snapshot_id, "levels_saved": len(levels)}


def get_microstructure_status(symbol: str) -> dict:
    initialize_database()
    normalized = symbol.upper()
    with connect() as connection:
        trade_row = connection.execute(
            """
            SELECT COUNT(*) AS row_count, MIN(event_time) AS first_time, MAX(event_time) AS last_time
            FROM market_aggregate_trades WHERE symbol = ?
            """,
            (normalized,),
        ).fetchone()
        snapshot_row = connection.execute(
            """
            SELECT COUNT(*) AS row_count, MIN(fetched_at) AS first_time, MAX(fetched_at) AS last_time
            FROM order_book_snapshots WHERE symbol = ?
            """,
            (normalized,),
        ).fetchone()
        delta_row = connection.execute(
            """
            SELECT COUNT(*) AS row_count, MIN(event_time) AS first_time, MAX(event_time) AS last_time
            FROM order_book_deltas WHERE symbol = ?
            """,
            (normalized,),
        ).fetchone()
    return {
        "symbol": normalized,
        "aggregate_trades": dict(trade_row),
        "order_book_snapshots": dict(snapshot_row),
        "order_book_deltas": dict(delta_row),
        "continuous_stream": int(delta_row["row_count"] or 0) > 0,
        "historical_l2_ready": int(delta_row["row_count"] or 0) >= 1000,
    }


def save_order_book_deltas(deltas: list[dict]) -> int:
    initialize_database()
    if not deltas:
        return 0
    with connect() as connection:
        before = connection.total_changes
        connection.executemany(
            """
            INSERT INTO order_book_deltas (
                symbol, event_time, first_update_id, final_update_id,
                bid_changes_json, ask_changes_json, level_change_count,
                source, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, final_update_id) DO NOTHING
            """,
            [
                (
                    item["symbol"], item["event_time"], item["first_update_id"],
                    item["final_update_id"], json.dumps(item["bid_changes"], ensure_ascii=True),
                    json.dumps(item["ask_changes"], ensure_ascii=True),
                    len(item["bid_changes"]) + len(item["ask_changes"]),
                    item.get("source", "binance_depth_stream"), item["received_at"],
                )
                for item in deltas
            ],
        )
        return connection.total_changes - before


def get_order_book_replay_anchor(symbol: str, target_time_iso: str) -> dict | None:
    initialize_database()
    normalized = symbol.upper()
    with connect() as connection:
        snapshot = connection.execute(
            """
            SELECT id, symbol, source, last_update_id, fetched_at
            FROM order_book_snapshots
            WHERE symbol = ? AND source = 'binance_depth_stream_local_book'
              AND last_update_id IS NOT NULL AND fetched_at <= ?
            ORDER BY fetched_at DESC, id DESC
            LIMIT 1
            """,
            (normalized, target_time_iso),
        ).fetchone()
        if not snapshot:
            return None
        levels = connection.execute(
            """
            SELECT side, level_index, price, quantity, notional
            FROM order_book_levels
            WHERE snapshot_id = ?
            ORDER BY side, level_index
            """,
            (snapshot["id"],),
        ).fetchall()
    payload = dict(snapshot)
    payload["bids"] = [dict(row) for row in levels if row["side"] == "bid"]
    payload["asks"] = [dict(row) for row in levels if row["side"] == "ask"]
    return payload


def list_order_book_deltas_for_replay(
    symbol: str,
    after_update_id: int,
    target_time_ms: int,
    limit: int = 50_001,
) -> list[dict]:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT event_time, first_update_id, final_update_id, bid_changes_json,
                   ask_changes_json, source, received_at
            FROM order_book_deltas
            WHERE symbol = ? AND final_update_id > ? AND event_time <= ?
            ORDER BY final_update_id
            LIMIT ?
            """,
            (symbol.upper(), int(after_update_id), int(target_time_ms), int(limit)),
        ).fetchall()
    return [
        {
            "symbol": symbol.upper(),
            "event_time": row["event_time"],
            "first_update_id": row["first_update_id"],
            "final_update_id": row["final_update_id"],
            "bid_changes": json.loads(row["bid_changes_json"]),
            "ask_changes": json.loads(row["ask_changes_json"]),
            "source": row["source"],
            "received_at": row["received_at"],
        }
        for row in rows
    ]


def prune_microstructure(symbol: str, trade_before_ms: int, delta_before_ms: int) -> dict:
    initialize_database()
    with connect() as connection:
        trade_cursor = connection.execute(
            "DELETE FROM market_aggregate_trades WHERE symbol = ? AND event_time < ?",
            (symbol.upper(), int(trade_before_ms)),
        )
        delta_cursor = connection.execute(
            "DELETE FROM order_book_deltas WHERE symbol = ? AND event_time < ?",
            (symbol.upper(), int(delta_before_ms)),
        )
    return {"trades_deleted": trade_cursor.rowcount, "deltas_deleted": delta_cursor.rowcount}


def start_collector_run(symbols: list[str], config: dict) -> int:
    initialize_database()
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO microstructure_collector_runs (
                symbols_json, status, config_json, started_at, updated_at
            ) VALUES (?, 'starting', ?, ?, ?)
            """,
            (json.dumps(symbols), json.dumps(config, ensure_ascii=True), now, now),
        )
        return int(cursor.lastrowid)


def update_collector_run(run_id: int, state: dict, status: str | None = None, stopped: bool = False) -> None:
    initialize_database()
    now = datetime.now(timezone.utc).isoformat()
    effective_status = status or state.get("status") or "running"
    with connect() as connection:
        connection.execute(
            """
            UPDATE microstructure_collector_runs SET
                status = ?, messages_received = ?, trades_saved = ?, deltas_saved = ?,
                snapshots_saved = ?, reconnect_count = ?, sequence_gap_count = ?,
                last_event_at = ?, last_error = ?, stopped_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                effective_status, int(state.get("messages_received", 0)),
                int(state.get("trades_saved", 0)), int(state.get("deltas_saved", 0)),
                int(state.get("snapshots_saved", 0)), int(state.get("reconnect_count", 0)),
                int(state.get("sequence_gap_count", 0)), state.get("last_event_at"),
                state.get("last_error"), now if stopped else None, now, run_id,
            ),
        )


def reconcile_interrupted_collectors() -> int:
    initialize_database()
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE microstructure_collector_runs
            SET status = 'interrupted', stopped_at = ?, updated_at = ?,
                last_error = COALESCE(last_error, 'Backend restarted while collector was active.')
            WHERE status IN ('starting', 'running', 'stopping')
            """,
            (now, now),
        )
        return cursor.rowcount


def latest_collector_run() -> dict | None:
    initialize_database()
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM microstructure_collector_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    payload = dict(row)
    payload["symbols"] = json.loads(payload.pop("symbols_json"))
    payload["config"] = json.loads(payload.pop("config_json"))
    return payload
