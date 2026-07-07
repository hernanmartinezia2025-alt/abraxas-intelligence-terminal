from __future__ import annotations

from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_asset_features(features: list[dict]) -> int:
    initialize_database()
    if not features:
        return 0

    created_at = utc_now_iso()
    rows = [{**feature, "created_at": created_at} for feature in features]
    with connect() as connection:
        connection.executemany(
            """
            INSERT INTO asset_features (
                symbol, timeframe, timestamp, return_1, return_5, return_20,
                volatility, z_score, drawdown, trend_strength, volume_change,
                risk_score, regime_label, created_at
            ) VALUES (
                :symbol, :timeframe, :timestamp, :return_1, :return_5, :return_20,
                :volatility, :z_score, :drawdown, :trend_strength, :volume_change,
                :risk_score, :regime_label, :created_at
            )
            ON CONFLICT(symbol, timeframe, timestamp) DO UPDATE SET
                return_1 = excluded.return_1,
                return_5 = excluded.return_5,
                return_20 = excluded.return_20,
                volatility = excluded.volatility,
                z_score = excluded.z_score,
                drawdown = excluded.drawdown,
                trend_strength = excluded.trend_strength,
                volume_change = excluded.volume_change,
                risk_score = excluded.risk_score,
                regime_label = excluded.regime_label,
                created_at = excluded.created_at
            """,
            rows,
        )
    return len(rows)


def list_asset_features(symbol: str | None = None, timeframe: str | None = None, limit: int = 250) -> list[dict]:
    initialize_database()
    params: list[object] = []
    where = []
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
            SELECT symbol, timeframe, timestamp, return_1, return_5, return_20,
                   volatility, z_score, drawdown, trend_strength, volume_change,
                   risk_score, regime_label, created_at
            FROM asset_features
            {where_sql}
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def latest_asset_features(symbol: str | None = None, timeframe: str | None = None, limit: int = 50) -> list[dict]:
    return list_asset_features(symbol=symbol, timeframe=timeframe, limit=limit)
