from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_regime_snapshot(snapshot: dict) -> int:
    initialize_database()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO regime_snapshots (
                symbol, timeframe, timestamp, regime_label, confidence, risk_score,
                market_bias, volatility_state, trend_state, drawdown_state,
                feature_count, reasons_json, reading, created_at
            ) VALUES (
                :symbol, :timeframe, :timestamp, :regime_label, :confidence, :risk_score,
                :market_bias, :volatility_state, :trend_state, :drawdown_state,
                :feature_count, :reasons_json, :reading, :created_at
            )
            ON CONFLICT(symbol, timeframe, timestamp) DO UPDATE SET
                regime_label = excluded.regime_label,
                confidence = excluded.confidence,
                risk_score = excluded.risk_score,
                market_bias = excluded.market_bias,
                volatility_state = excluded.volatility_state,
                trend_state = excluded.trend_state,
                drawdown_state = excluded.drawdown_state,
                feature_count = excluded.feature_count,
                reasons_json = excluded.reasons_json,
                reading = excluded.reading,
                created_at = excluded.created_at
            """,
            {
                **snapshot,
                "reasons_json": json.dumps(snapshot.get("reasons") or [], ensure_ascii=True),
                "created_at": utc_now_iso(),
            },
        )
        row = connection.execute(
            """
            SELECT id FROM regime_snapshots
            WHERE symbol = ? AND timeframe = ? AND timestamp = ?
            """,
            (snapshot["symbol"], snapshot["timeframe"], snapshot["timestamp"]),
        ).fetchone()
    return int(row["id"]) if row else 0


def list_regime_snapshots(symbol: str | None = None, timeframe: str | None = None, limit: int = 100) -> list[dict]:
    initialize_database()
    where = []
    params: list[object] = []
    if symbol:
        where.append("symbol = ?")
        params.append(symbol.upper())
    if timeframe:
        where.append("timeframe = ?")
        params.append(timeframe)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    params.append(limit)

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, symbol, timeframe, timestamp, regime_label, confidence, risk_score,
                   market_bias, volatility_state, trend_state, drawdown_state,
                   feature_count, reasons_json, reading, created_at
            FROM regime_snapshots
            {where_sql}
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [normalize_snapshot(dict(row)) for row in rows]


def normalize_snapshot(row: dict) -> dict:
    try:
        row["reasons"] = json.loads(row.pop("reasons_json") or "[]")
    except json.JSONDecodeError:
        row["reasons"] = []
    return row
