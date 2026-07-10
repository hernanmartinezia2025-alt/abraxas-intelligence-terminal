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
    created_at = utc_now_iso()
    profit_factor_value = metrics.get("profit_factor")
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
                "profit_factor": float(profit_factor_value) if profit_factor_value is not None else None,
                "metrics_json": json.dumps(metrics, ensure_ascii=True),
                "trades_json": json.dumps(trades, ensure_ascii=True),
                "equity_curve_json": json.dumps(equity_curve, ensure_ascii=True),
                "created_at": created_at,
            },
        )
        backtest_id = int(cursor.lastrowid)

        trade_rows = []
        for trade_index, trade in enumerate(trades, start=1):
            trade_rows.append(
                {
                    "backtest_id": backtest_id,
                    "bot_id": int(result["bot_id"]),
                    "bot_version_id": int(result["bot_version_id"]),
                    "trade_index": int(trade.get("trade_index") or trade_index),
                    "side": str(trade.get("side") or "long"),
                    "entry_signal_timestamp": trade.get("entry_signal_timestamp"),
                    "exit_signal_timestamp": trade.get("exit_signal_timestamp"),
                    "entry_timestamp": int(trade["entry_timestamp"]),
                    "exit_timestamp": int(trade["exit_timestamp"]),
                    "entry_price": float(trade["entry_price"]),
                    "exit_price": float(trade["exit_price"]),
                    "quantity": float(trade["quantity"]),
                    "allocated_equity": trade.get("allocated_equity"),
                    "gross_pnl": trade.get("gross_pnl"),
                    "entry_fee": trade.get("entry_fee"),
                    "exit_fee": trade.get("exit_fee"),
                    "fees_paid": trade.get("fees_paid"),
                    "slippage_cost": trade.get("slippage_cost"),
                    "pnl": float(trade.get("pnl") or 0),
                    "return_pct": float(trade.get("return_pct") or 0),
                    "bars_held": trade.get("bars_held"),
                    "exit_reason": trade.get("exit_reason"),
                    "forced_exit": int(bool(trade.get("forced_exit"))),
                    "created_at": created_at,
                }
            )
        if trade_rows:
            connection.executemany(
                """
                INSERT INTO backtest_trades (
                    backtest_id, bot_id, bot_version_id, trade_index, side,
                    entry_signal_timestamp, exit_signal_timestamp, entry_timestamp,
                    exit_timestamp, entry_price, exit_price, quantity, allocated_equity,
                    gross_pnl, entry_fee, exit_fee, fees_paid, slippage_cost, pnl,
                    return_pct, bars_held, exit_reason, forced_exit, created_at
                ) VALUES (
                    :backtest_id, :bot_id, :bot_version_id, :trade_index, :side,
                    :entry_signal_timestamp, :exit_signal_timestamp, :entry_timestamp,
                    :exit_timestamp, :entry_price, :exit_price, :quantity, :allocated_equity,
                    :gross_pnl, :entry_fee, :exit_fee, :fees_paid, :slippage_cost, :pnl,
                    :return_pct, :bars_held, :exit_reason, :forced_exit, :created_at
                )
                """,
                trade_rows,
            )

        equity_rows = []
        for point_index, point in enumerate(equity_curve, start=1):
            equity_rows.append(
                {
                    "backtest_id": backtest_id,
                    "bot_id": int(result["bot_id"]),
                    "bot_version_id": int(result["bot_version_id"]),
                    "point_index": int(point.get("point_index") or point_index),
                    "timestamp": int(point["timestamp"]),
                    "equity": float(point["equity"]),
                    "benchmark_equity": point.get("benchmark_equity"),
                    "close": float(point["close"]),
                    "drawdown_pct": point.get("drawdown_pct"),
                    "in_position": int(bool(point.get("in_position"))),
                    "created_at": created_at,
                }
            )
        if equity_rows:
            connection.executemany(
                """
                INSERT INTO backtest_equity (
                    backtest_id, bot_id, bot_version_id, point_index, timestamp,
                    equity, benchmark_equity, close, drawdown_pct, in_position, created_at
                ) VALUES (
                    :backtest_id, :bot_id, :bot_version_id, :point_index, :timestamp,
                    :equity, :benchmark_equity, :close, :drawdown_pct, :in_position, :created_at
                )
                """,
                equity_rows,
            )
        return backtest_id


def parse_json(value: object, fallback: object) -> object:
    try:
        return json.loads(str(value)) if value else fallback
    except (json.JSONDecodeError, TypeError, ValueError):
        return fallback


def optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def normalize_backtest(row: dict, include_payload: bool = False) -> dict:
    metrics = parse_json(row.get("metrics_json"), {})
    if not isinstance(metrics, dict):
        metrics = {}
    metric_profit_factor = metrics.get("profit_factor")
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
        "profit_factor": optional_float(metric_profit_factor) if "profit_factor" in metrics else float(row["profit_factor"]),
        "benchmark_roi_pct": optional_float(metrics.get("benchmark_roi_pct")),
        "alpha_pct": optional_float(metrics.get("alpha_pct")),
        "total_fees": optional_float(metrics.get("total_fees")),
        "fee_pct": optional_float(metrics.get("fee_pct")),
        "slippage_pct": optional_float(metrics.get("slippage_pct")),
        "warning_count": len(metrics.get("warnings") or []),
        "engine_version": metrics.get("engine_version") or "1.0",
        "execution_model": metrics.get("execution_model") or "same_close_legacy",
        "created_at": row["created_at"],
    }
    if include_payload:
        normalized["metrics"] = metrics
        normalized["warnings"] = metrics.get("warnings") or []
        normalized["data_quality"] = metrics.get("data_quality") or {}
        normalized["trades"] = parse_json(row.get("trades_json"), [])
        normalized["equity_curve"] = parse_json(row.get("equity_curve_json"), [])
    return normalized


def normalize_trade(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "backtest_id": int(row["backtest_id"]),
        "bot_id": int(row["bot_id"]),
        "bot_version_id": int(row["bot_version_id"]),
        "trade_index": int(row["trade_index"]),
        "side": row["side"],
        "entry_signal_timestamp": row["entry_signal_timestamp"],
        "exit_signal_timestamp": row["exit_signal_timestamp"],
        "entry_timestamp": int(row["entry_timestamp"]),
        "exit_timestamp": int(row["exit_timestamp"]),
        "entry_price": float(row["entry_price"]),
        "exit_price": float(row["exit_price"]),
        "quantity": float(row["quantity"]),
        "allocated_equity": optional_float(row["allocated_equity"]),
        "gross_pnl": optional_float(row["gross_pnl"]),
        "entry_fee": optional_float(row["entry_fee"]),
        "exit_fee": optional_float(row["exit_fee"]),
        "fees_paid": optional_float(row["fees_paid"]),
        "slippage_cost": optional_float(row["slippage_cost"]),
        "pnl": float(row["pnl"]),
        "return_pct": float(row["return_pct"]),
        "bars_held": int(row["bars_held"]) if row["bars_held"] is not None else None,
        "exit_reason": row["exit_reason"],
        "forced_exit": bool(row["forced_exit"]),
    }


def normalize_equity_point(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "backtest_id": int(row["backtest_id"]),
        "bot_id": int(row["bot_id"]),
        "bot_version_id": int(row["bot_version_id"]),
        "point_index": int(row["point_index"]),
        "timestamp": int(row["timestamp"]),
        "equity": float(row["equity"]),
        "benchmark_equity": optional_float(row["benchmark_equity"]),
        "close": float(row["close"]),
        "drawdown_pct": optional_float(row["drawdown_pct"]),
        "in_position": bool(row["in_position"]),
    }


def list_backtests(bot_id: int | None = None, limit: int = 100) -> dict:
    initialize_database()
    where = ""
    params: list[object] = []
    if bot_id is not None:
        where = "WHERE bot_id = ?"
        params.append(bot_id)
    params.append(limit)
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, bot_id, bot_version_id, symbol, timeframe, input_start, input_end,
                   initial_equity, final_equity, roi_pct, max_drawdown_pct, total_trades,
                   win_rate_pct, profit_factor, metrics_json, created_at
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
        trade_rows = connection.execute(
            """
            SELECT id, backtest_id, bot_id, bot_version_id, trade_index, side,
                   entry_signal_timestamp, exit_signal_timestamp, entry_timestamp,
                   exit_timestamp, entry_price, exit_price, quantity, allocated_equity,
                   gross_pnl, entry_fee, exit_fee, fees_paid, slippage_cost, pnl,
                   return_pct, bars_held, exit_reason, forced_exit
            FROM backtest_trades
            WHERE backtest_id = ?
            ORDER BY trade_index
            """,
            (backtest_id,),
        ).fetchall()
        equity_rows = connection.execute(
            """
            SELECT id, backtest_id, bot_id, bot_version_id, point_index, timestamp,
                   equity, benchmark_equity, close, drawdown_pct, in_position
            FROM backtest_equity
            WHERE backtest_id = ?
            ORDER BY point_index
            """,
            (backtest_id,),
        ).fetchall()
    if not row:
        raise ValueError("Backtest not found")
    normalized = normalize_backtest(dict(row), include_payload=True)
    if trade_rows:
        normalized["trades"] = [normalize_trade(dict(trade)) for trade in trade_rows]
    if equity_rows:
        normalized["equity_curve"] = [normalize_equity_point(dict(point)) for point in equity_rows]
    return normalized
