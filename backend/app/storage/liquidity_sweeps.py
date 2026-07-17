from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def _normalize(row: dict) -> dict:
    payload = json.loads(row.pop("result_json"))
    return {
        **row,
        "id": int(row["id"]),
        "order_allowed": bool(row["order_allowed"]),
        "result": payload,
    }


def save_liquidity_sweep_evaluation(payload: dict) -> dict:
    initialize_database()
    candle_timestamp = int(payload["evidence"]["sweep"].get("candle_timestamp") or 0)
    key = hashlib.sha256(
        f"{payload['contract']}:{payload['symbol']}:{payload['timeframe']}:{candle_timestamp}".encode("utf-8")
    ).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO liquidity_sweep_evaluations (
                evaluation_key, symbol, timeframe, candle_timestamp, state,
                direction, order_allowed, result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(evaluation_key) DO UPDATE SET
                state = excluded.state,
                direction = excluded.direction,
                order_allowed = excluded.order_allowed,
                result_json = excluded.result_json,
                created_at = excluded.created_at
            """,
            (
                key, payload["symbol"], payload["timeframe"], candle_timestamp,
                payload["state"], payload["direction"], int(payload["order_allowed"]),
                json.dumps(payload, ensure_ascii=True), now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM liquidity_sweep_evaluations WHERE evaluation_key = ?", (key,)
        ).fetchone()
    return _normalize(dict(row))


def list_liquidity_sweep_evaluations(limit: int = 20, symbol: str = "") -> dict:
    initialize_database()
    with connect() as connection:
        if symbol:
            rows = connection.execute(
                "SELECT * FROM liquidity_sweep_evaluations WHERE symbol = ? ORDER BY id DESC LIMIT ?",
                (symbol.upper(), limit),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM liquidity_sweep_evaluations ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    evaluations = [_normalize(dict(row)) for row in rows]
    return {"evaluations": evaluations, "count": len(evaluations), "limit": limit}
