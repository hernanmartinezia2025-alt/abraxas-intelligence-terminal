from __future__ import annotations

import math
from statistics import median


OPERATORS = {
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
}


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


def rule_passes(row: dict, rule: dict) -> bool:
    field = str(rule.get("field") or "")
    operator = str(rule.get("operator") or "")
    if operator not in OPERATORS or field not in row:
        return False
    left = row[field]
    right = rule.get("value")
    if isinstance(left, str):
        return OPERATORS[operator](left, str(right))
    return OPERATORS[operator](safe_float(left), safe_float(right))


def rules_pass(row: dict, rules: list[dict]) -> bool:
    if not rules:
        return False
    return all(rule_passes(row, rule) for rule in rules)


def max_drawdown_pct(equity_curve: list[dict]) -> float:
    peak = None
    max_drawdown = 0.0
    for point in equity_curve:
        equity = safe_float(point.get("equity"))
        peak = equity if peak is None else max(peak, equity)
        if peak:
            drawdown = ((equity / peak) - 1) * 100
            max_drawdown = min(max_drawdown, drawdown)
    return round(max_drawdown, 4)


def profit_factor(trades: list[dict]) -> float | None:
    gross_profit = sum(max(0.0, safe_float(trade.get("pnl"))) for trade in trades)
    gross_loss = abs(sum(min(0.0, safe_float(trade.get("pnl"))) for trade in trades))
    if gross_loss == 0:
        return None
    return round(gross_profit / gross_loss, 4)


def warning(code: str, message: str, severity: str = "warning") -> dict:
    return {"code": code, "message": message, "severity": severity}


def normalize_rows(rows: list[dict]) -> tuple[list[dict], dict]:
    by_timestamp: dict[int, dict] = {}
    invalid_rows = 0
    duplicate_timestamps = 0
    for row in rows:
        try:
            timestamp = int(row["timestamp"])
        except (KeyError, TypeError, ValueError):
            invalid_rows += 1
            continue
        close = safe_float(row.get("close"))
        open_price = safe_float(row.get("open"), close)
        if timestamp <= 0 or close <= 0 or open_price <= 0:
            invalid_rows += 1
            continue
        if timestamp in by_timestamp:
            duplicate_timestamps += 1
        by_timestamp[timestamp] = {
            **row,
            "timestamp": timestamp,
            "open": open_price,
            "high": safe_float(row.get("high"), max(open_price, close)),
            "low": safe_float(row.get("low"), min(open_price, close)),
            "close": close,
        }

    ordered = [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]
    intervals = [
        ordered[index]["timestamp"] - ordered[index - 1]["timestamp"]
        for index in range(1, len(ordered))
        if ordered[index]["timestamp"] > ordered[index - 1]["timestamp"]
    ]
    expected_interval_ms = int(median(intervals)) if intervals else 0
    gap_count = 0
    if expected_interval_ms > 0:
        for interval in intervals:
            if interval > expected_interval_ms * 1.5:
                gap_count += max(1, int(round(interval / expected_interval_ms)) - 1)

    return ordered, {
        "rows_received": len(rows),
        "rows_used": len(ordered),
        "invalid_rows": invalid_rows,
        "duplicate_timestamps": duplicate_timestamps,
        "gap_count": gap_count,
        "expected_interval_ms": expected_interval_ms,
    }


def run_backtest(
    bot: dict,
    version: dict,
    rows: list[dict],
    initial_equity: float = 10_000.0,
    fee_pct: float = 0.1,
    slippage_pct: float = 0.05,
    requested_limit: int | None = None,
) -> dict:
    if initial_equity <= 0:
        raise ValueError("Initial equity must be greater than zero")
    if fee_pct < 0 or slippage_pct < 0:
        raise ValueError("Fee and slippage must be non-negative")

    ordered_rows, data_quality = normalize_rows(rows)
    if len(ordered_rows) < 40:
        raise ValueError(f"Not enough feature rows for backtest: {len(ordered_rows)} available, 40 required")

    strategy = version.get("strategy") or {}
    risk = strategy.get("risk") or {}
    entry_rules = strategy.get("entry") or []
    exit_rules = strategy.get("exit") or []
    max_position_pct = min(100.0, max(0.0, safe_float(risk.get("max_position_pct"), 10.0)))
    stop_loss_pct = abs(safe_float(risk.get("stop_loss_pct"), 2.0))
    take_profit_pct = abs(safe_float(risk.get("take_profit_pct"), 4.0))

    equity = float(initial_equity)
    position = None
    pending_entry = None
    pending_exit = None
    trades: list[dict] = []
    equity_curve: list[dict] = []
    warnings: list[dict] = []
    peak_equity = float(initial_equity)
    benchmark_start_price = safe_float(ordered_rows[0].get("close"))

    if len(ordered_rows) < 100:
        warnings.append(
            warning(
                "LOW_DATA_SAMPLE",
                f"Only {len(ordered_rows)} usable rows are available; results are exploratory.",
            )
        )
    if data_quality["invalid_rows"]:
        warnings.append(
            warning(
                "INVALID_ROWS_EXCLUDED",
                f"{data_quality['invalid_rows']} invalid rows were excluded before execution.",
            )
        )
    if data_quality["duplicate_timestamps"]:
        warnings.append(
            warning(
                "DUPLICATE_TIMESTAMPS",
                f"{data_quality['duplicate_timestamps']} duplicate timestamps were collapsed.",
            )
        )
    if data_quality["gap_count"]:
        warnings.append(
            warning(
                "DATA_GAPS",
                f"Detected approximately {data_quality['gap_count']} missing bars in the requested range.",
            )
        )

    def close_position(
        exit_reference_price: float,
        exit_timestamp: int,
        exit_index: int,
        exit_reason: str,
        forced_exit: bool,
        exit_signal_timestamp: int | None,
    ) -> None:
        nonlocal equity, position
        if not position:
            return
        exit_price = exit_reference_price * (1 - slippage_pct / 100)
        exit_notional = position["quantity"] * exit_price
        exit_fee = exit_notional * (fee_pct / 100)
        gross_pnl = position["quantity"] * (exit_price - position["entry_price"])
        net_pnl = gross_pnl - position["entry_fee"] - exit_fee
        exit_slippage = position["quantity"] * max(0.0, exit_reference_price - exit_price)
        equity += gross_pnl - exit_fee
        trades.append(
            {
                "trade_index": len(trades) + 1,
                "side": "long",
                "entry_signal_timestamp": position["entry_signal_timestamp"],
                "exit_signal_timestamp": exit_signal_timestamp,
                "entry_timestamp": position["entry_timestamp"],
                "exit_timestamp": exit_timestamp,
                "entry_price": round(position["entry_price"], 8),
                "exit_price": round(exit_price, 8),
                "quantity": round(position["quantity"], 8),
                "allocated_equity": round(position["allocated_equity"], 4),
                "gross_pnl": round(gross_pnl, 4),
                "entry_fee": round(position["entry_fee"], 4),
                "exit_fee": round(exit_fee, 4),
                "fees_paid": round(position["entry_fee"] + exit_fee, 4),
                "slippage_cost": round(position["entry_slippage"] + exit_slippage, 4),
                "pnl": round(net_pnl, 4),
                "return_pct": round((net_pnl / position["allocated_equity"]) * 100, 4),
                "bars_held": max(0, exit_index - position["entry_index"]),
                "exit_reason": exit_reason,
                "forced_exit": forced_exit,
            }
        )
        position = None

    for index, row in enumerate(ordered_rows):
        timestamp = int(row["timestamp"])
        open_price = safe_float(row.get("open"), safe_float(row.get("close")))
        close_price = safe_float(row.get("close"))

        if pending_exit and position:
            close_position(
                exit_reference_price=open_price,
                exit_timestamp=timestamp,
                exit_index=index,
                exit_reason=pending_exit["reason"],
                forced_exit=False,
                exit_signal_timestamp=pending_exit["signal_timestamp"],
            )
            pending_exit = None

        if pending_entry and not position and max_position_pct > 0:
            if equity <= 0:
                if not any(item["code"] == "INSUFFICIENT_EQUITY" for item in warnings):
                    warnings.append(
                        warning(
                            "INSUFFICIENT_EQUITY",
                            "A pending entry was rejected because no positive equity remained.",
                        )
                    )
                pending_entry = None
            else:
                entry_price = open_price * (1 + slippage_pct / 100)
                allocated_equity = equity * (max_position_pct / 100)
                fee_rate = fee_pct / 100
                entry_notional = allocated_equity / (1 + fee_rate)
                entry_fee = entry_notional * fee_rate
                quantity = entry_notional / entry_price
                position = {
                    "entry_signal_timestamp": pending_entry["signal_timestamp"],
                    "entry_timestamp": timestamp,
                    "entry_price": entry_price,
                    "entry_reference_price": open_price,
                    "entry_slippage": quantity * max(0.0, entry_price - open_price),
                    "entry_fee": entry_fee,
                    "quantity": quantity,
                    "allocated_equity": allocated_equity,
                    "entry_index": index,
                }
                equity -= entry_fee
                pending_entry = None

        marked_equity = equity
        if position:
            marked_equity += position["quantity"] * (close_price - position["entry_price"])
        benchmark_equity = initial_equity * (close_price / benchmark_start_price)
        peak_equity = max(peak_equity, marked_equity)
        drawdown_pct = ((marked_equity / peak_equity) - 1) * 100 if peak_equity else 0.0
        equity_curve.append(
            {
                "point_index": len(equity_curve) + 1,
                "timestamp": timestamp,
                "equity": round(marked_equity, 4),
                "benchmark_equity": round(benchmark_equity, 4),
                "close": round(close_price, 8),
                "drawdown_pct": round(drawdown_pct, 4),
                "in_position": bool(position),
            }
        )

        if position:
            unrealized_return = ((close_price / position["entry_price"]) - 1) * 100
            exit_reason = None
            if unrealized_return <= -stop_loss_pct:
                exit_reason = "stop_loss"
            elif unrealized_return >= take_profit_pct:
                exit_reason = "take_profit"
            elif rules_pass(row, exit_rules):
                exit_reason = "signal"
            if exit_reason:
                pending_exit = {"reason": exit_reason, "signal_timestamp": timestamp}
        elif not pending_entry and rules_pass(row, entry_rules):
            pending_entry = {"signal_timestamp": timestamp}

    if position:
        last_row = ordered_rows[-1]
        close_position(
            exit_reference_price=safe_float(last_row.get("close")),
            exit_timestamp=int(last_row["timestamp"]),
            exit_index=len(ordered_rows) - 1,
            exit_reason="end_of_data",
            forced_exit=True,
            exit_signal_timestamp=(pending_exit or {}).get("signal_timestamp"),
        )
        prior_peak = max([initial_equity, *[safe_float(point.get("equity")) for point in equity_curve[:-1]]])
        final_peak = max(prior_peak, equity)
        equity_curve[-1] = {
            **equity_curve[-1],
            "equity": round(equity, 4),
            "drawdown_pct": round(((equity / final_peak) - 1) * 100 if final_peak else 0.0, 4),
            "in_position": False,
        }
        warnings.append(warning("FORCED_EXIT_AT_END", "An open long position was closed at the final available close."))

    if pending_entry:
        warnings.append(warning("PENDING_ENTRY_DROPPED", "The final entry signal had no next bar available for execution."))

    wins = [trade for trade in trades if safe_float(trade.get("pnl")) > 0]
    gross_profit = sum(max(0.0, safe_float(trade.get("pnl"))) for trade in trades)
    gross_loss = abs(sum(min(0.0, safe_float(trade.get("pnl"))) for trade in trades))
    total_fees = sum(safe_float(trade.get("fees_paid")) for trade in trades)
    total_slippage = sum(safe_float(trade.get("slippage_cost")) for trade in trades)
    benchmark_final_equity = safe_float(equity_curve[-1].get("benchmark_equity"), initial_equity)
    roi_pct = ((equity / initial_equity) - 1) * 100
    benchmark_roi_pct = ((benchmark_final_equity / initial_equity) - 1) * 100
    alpha_pct = roi_pct - benchmark_roi_pct
    computed_profit_factor = profit_factor(trades)

    if not trades:
        warnings.append(warning("NO_TRADES", "The strategy produced no completed trades for this sample."))
    elif len(trades) < 10:
        warnings.append(warning("LOW_TRADE_COUNT", f"Only {len(trades)} trades completed; confidence is low."))
    if computed_profit_factor is None and gross_profit > 0:
        warnings.append(
            warning(
                "PROFIT_FACTOR_UNDEFINED",
                "Profit factor is undefined because the sample contains no losing trades.",
                severity="info",
            )
        )
    if alpha_pct < 0:
        warnings.append(
            warning(
                "UNDERPERFORMS_BENCHMARK",
                "The strategy underperformed the frictionless buy-and-hold benchmark over the same range.",
                severity="info",
            )
        )

    data_quality["requested_limit"] = requested_limit
    metrics = {
        "roi_pct": round(roi_pct, 4),
        "benchmark_roi_pct": round(benchmark_roi_pct, 4),
        "benchmark_final_equity": round(benchmark_final_equity, 4),
        "alpha_pct": round(alpha_pct, 4),
        "max_drawdown_pct": max_drawdown_pct(equity_curve),
        "total_trades": len(trades),
        "win_rate_pct": round((len(wins) / len(trades)) * 100, 4) if trades else 0.0,
        "profit_factor": computed_profit_factor,
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "net_pnl": round(equity - initial_equity, 4),
        "total_fees": round(total_fees, 4),
        "estimated_slippage_cost": round(total_slippage, 4),
        "fee_pct": fee_pct,
        "slippage_pct": slippage_pct,
        "max_position_pct": max_position_pct,
        "data_points": len(ordered_rows),
        "engine_version": "2.0",
        "execution_model": "signal_close_fill_next_open",
        "position_mode": "long_only",
        "benchmark_model": "frictionless_buy_and_hold",
        "data_quality": data_quality,
        "warnings": warnings,
    }

    return {
        "bot_id": bot["id"],
        "bot_version_id": version["id"],
        "symbol": bot["base_symbol"],
        "timeframe": bot["timeframe"],
        "input_start": ordered_rows[0]["timestamp"],
        "input_end": ordered_rows[-1]["timestamp"],
        "initial_equity": round(initial_equity, 4),
        "final_equity": round(equity, 4),
        "metrics": metrics,
        "warnings": warnings,
        "data_quality": data_quality,
        "trades": trades,
        "equity_curve": equity_curve,
    }
