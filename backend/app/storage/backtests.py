from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_backtest_run(result: dict) -> int:
    initialize_database()
    metrics = result.get("metrics") or {}
    trades = result.get("trades") or []
    equity_curve = result.get("equity_curve") or []
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO backtest_runs (
                bot_id, bot_version_id, symbol, timeframe, input_start, input_end,
                initial_equity, final_equity, roi_pct, max_drawdown_pct,
                total_trades, win_rate_pct, profit_factor,
                metrics_json, trades_json, equity_curve_json, created_at
            ) VALUES (
                :bot_id, :bot_version_id, :symbol, :timeframe, :input_start, :input_end,
                :initial_equity, :final_equity, :roi_pct, :max_drawdown_pct,
                :total_trades, :win_rate_pct, :profit_factor,
                :metrics_json, :trades_json, :equity_curve_json, :created_at
            )
            """,
            {
                "bot_id": int(result["bot_id"]),
                "bot_version_id": int(result["bot_version_id"]),
                "symbol": result["symbol"],
                "timeframe": result["timeframe"],
                "input_start": result.get("input_start"),
                "input_end": result.get("input_end"),
                "initial_equity": float(result["initial_equity"]),
                "final_equity": float(result["final_equity"]),
                "roi_pct": float(metrics.get("roi_pct") or 0),
                "max_drawdown_pct": float(metrics.get("max_drawdown_pct") or 0),
                "total_trades": int(metrics.get("total_trades") or 0),
                "win_rate_pct": float(metrics.get("win_rate_pct") or 0),
                "profit_factor": float(metrics.get("profit_factor") or 0),
                "metrics_json": json.dumps(metrics, ensure_ascii=True),
                "trades_json": json.dumps(trades, ensure_ascii=True),
                "equity_curve_json": json.dumps(equity_curve, ensure_ascii=True),
                "created_at": utc_now_iso(),
            },
        )
        return int(cursor.lastrowid)


def normalize_backtest(row: dict, include_payload: bool = False) -> dict:
    normalized = {
        "id": int(row["id"]),
        "bot_id": int(row["bot_id"]),
        "bot_version_id": int(row["bot_version_id"]),
        "symbol": row["symbol"],
        "timeframe": row["timeframe"],
        "input_start": row["input_start"],
        "input_end": row["input_end"],
        "initial_equity": float(row["initial_equity"]),
        "final_equity": float(row["final_equity"]),
        "roi_pct": float(row["roi_pct"]),
        "max_drawdown_pct": float(row["max_drawdown_pct"]),
        "total_trades": int(row["total_trades"]),
        "win_rate_pct": float(row["win_rate_pct"]),
        "profit_factor": float(row["profit_factor"]),
        "created_at": row["created_at"],
    }
    if include_payload:
        for key in ("metrics", "trades", "equity_curve"):
            raw_key = f"{key}_json"
            try:
                fallback = "{}" if key == "metrics" else "[]"
                normalized[key] = json.loads(row.get(raw_key) or fallback)
            except json.JSONDecodeError:
                normalized[key] = {} if key == "metrics" else []
    return normalized


def list_backtests(bot_id: int | None = None, limit: int = 100) -> dict:
    initialize_database()
    where = ""
    params: list[object] = []
    if bot_id:
        where = "WHERE bot_id = ?"
        params.append(bot_id)
    params.append(limit)
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, bot_id, bot_version_id, symbol, timeframe, input_start, input_end,
                   initial_equity, final_equity, roi_pct, max_drawdown_pct, total_trades,
                   win_rate_pct, profit_factor, created_at
            FROM backtest_runs
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    runs = [normalize_backtest(dict(row)) for row in rows]
    return {"runs": runs, "count": len(runs), "limit": limit, "bot_id": bot_id}


def get_backtest(backtest_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT id, bot_id, bot_version_id, symbol, timeframe, input_start, input_end,
                   initial_equity, final_equity, roi_pct, max_drawdown_pct, total_trades,
                   win_rate_pct, profit_factor, metrics_json, trades_json,
                   equity_curve_json, created_at
            FROM backtest_runs
            WHERE id = ?
            """,
            (backtest_id,),
        ).fetchone()
    if not row:
        raise ValueError("Backtest not found")
    return normalize_backtest(dict(row), include_payload=True)
