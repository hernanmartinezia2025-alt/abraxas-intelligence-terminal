from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def candle_time_range(candles: list[dict]) -> tuple[int | None, int | None]:
    if not candles:
        return None, None
    timestamps = [int(candle["timestamp"]) for candle in candles if candle.get("timestamp") is not None]
    if not timestamps:
        return None, None
    return min(timestamps), max(timestamps)


def save_statistics_run(
    symbol: str,
    timeframe: str,
    run_type: str,
    metrics: dict,
    candles: list[dict],
) -> int:
    initialize_database()
    input_start, input_end = candle_time_range(candles)
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO statistics_runs (
                symbol, timeframe, run_type, input_start, input_end, metrics_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol.upper(),
                timeframe,
                run_type,
                input_start,
                input_end,
                json.dumps(metrics, ensure_ascii=True),
                utc_now_iso(),
            ),
        )
        return int(cursor.lastrowid)


def list_statistics_runs(
    symbol: str | None = None,
    timeframe: str | None = None,
    run_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    initialize_database()
    where = []
    params: list[object] = []
    if symbol:
        where.append("symbol = ?")
        params.append(symbol.upper())
    if timeframe:
        where.append("timeframe = ?")
        params.append(timeframe)
    if run_type:
        where.append("run_type = ?")
        params.append(run_type)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    params.append(limit)

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, symbol, timeframe, run_type, input_start, input_end,
                   metrics_json, created_at
            FROM statistics_runs
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [normalize_run(dict(row)) for row in rows]


def normalize_run(row: dict) -> dict:
    try:
        row["metrics"] = json.loads(row.pop("metrics_json") or "{}")
    except json.JSONDecodeError:
        row["metrics"] = {}
    return row
