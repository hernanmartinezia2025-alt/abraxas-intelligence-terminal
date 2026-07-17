from __future__ import annotations

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
    return {
        "symbol": normalized,
        "aggregate_trades": dict(trade_row),
        "order_book_snapshots": dict(snapshot_row),
        "continuous_stream": False,
        "historical_l2_ready": int(snapshot_row["row_count"] or 0) >= 100,
    }
