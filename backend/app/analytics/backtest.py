from __future__ import annotations

import math


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


def profit_factor(trades: list[dict]) -> float:
    gross_profit = sum(max(0.0, safe_float(trade.get("pnl"))) for trade in trades)
    gross_loss = abs(sum(min(0.0, safe_float(trade.get("pnl"))) for trade in trades))
    if gross_loss == 0:
        return round(gross_profit, 4) if gross_profit else 0.0
    return round(gross_profit / gross_loss, 4)


def run_backtest(
    bot: dict,
    version: dict,
    rows: list[dict],
    initial_equity: float = 10_000.0,
    fee_pct: float = 0.1,
    slippage_pct: float = 0.05,
) -> dict:
    if len(rows) < 40:
        raise ValueError("Not enough feature rows for backtest")

    strategy = version.get("strategy") or {}
    risk = strategy.get("risk") or {}
    entry_rules = strategy.get("entry") or []
    exit_rules = strategy.get("exit") or []
    max_position_pct = safe_float(risk.get("max_position_pct"), 10.0)
    stop_loss_pct = abs(safe_float(risk.get("stop_loss_pct"), 2.0))
    take_profit_pct = abs(safe_float(risk.get("take_profit_pct"), 4.0))

    equity = float(initial_equity)
    position = None
    trades: list[dict] = []
    equity_curve: list[dict] = []

    ordered_rows = sorted(rows, key=lambda item: int(item["timestamp"]))
    for row in ordered_rows:
        price = safe_float(row.get("close"))
        if price <= 0:
            continue

        unrealized_equity = equity
        if position:
            unrealized_return = ((price / position["entry_price"]) - 1) * 100
            unrealized_equity = equity + position["quantity"] * (price - position["entry_price"])
            should_exit = (
                rules_pass(row, exit_rules)
                or unrealized_return <= -stop_loss_pct
                or unrealized_return >= take_profit_pct
            )
            if should_exit:
                exit_price = price * (1 - slippage_pct / 100)
                gross_pnl = position["quantity"] * (exit_price - position["entry_price"])
                exit_fee = position["quantity"] * exit_price * (fee_pct / 100)
                pnl = gross_pnl - exit_fee
                equity += pnl
                trades.append(
                    {
                        "entry_timestamp": position["entry_timestamp"],
                        "exit_timestamp": row["timestamp"],
                        "entry_price": round(position["entry_price"], 8),
                        "exit_price": round(exit_price, 8),
                        "quantity": round(position["quantity"], 8),
                        "pnl": round(pnl, 4),
                        "return_pct": round((pnl / position["allocated_equity"]) * 100, 4),
                    }
                )
                position = None
                unrealized_equity = equity

        if not position and rules_pass(row, entry_rules):
            entry_price = price * (1 + slippage_pct / 100)
            allocated_equity = equity * (max_position_pct / 100)
            entry_fee = allocated_equity * (fee_pct / 100)
            quantity = (allocated_equity - entry_fee) / entry_price
            position = {
                "entry_timestamp": row["timestamp"],
                "entry_price": entry_price,
                "quantity": quantity,
                "allocated_equity": allocated_equity,
            }
            equity -= entry_fee
            unrealized_equity = equity

        equity_curve.append(
            {
                "timestamp": row["timestamp"],
                "equity": round(unrealized_equity, 4),
                "close": round(price, 8),
                "in_position": bool(position),
            }
        )

    if position:
        last_row = ordered_rows[-1]
        exit_price = safe_float(last_row.get("close")) * (1 - slippage_pct / 100)
        gross_pnl = position["quantity"] * (exit_price - position["entry_price"])
        exit_fee = position["quantity"] * exit_price * (fee_pct / 100)
        pnl = gross_pnl - exit_fee
        equity += pnl
        trades.append(
            {
                "entry_timestamp": position["entry_timestamp"],
                "exit_timestamp": last_row["timestamp"],
                "entry_price": round(position["entry_price"], 8),
                "exit_price": round(exit_price, 8),
                "quantity": round(position["quantity"], 8),
                "pnl": round(pnl, 4),
                "return_pct": round((pnl / position["allocated_equity"]) * 100, 4),
                "forced_exit": True,
            }
        )
        equity_curve.append(
            {
                "timestamp": last_row["timestamp"],
                "equity": round(equity, 4),
                "close": round(exit_price, 8),
                "in_position": False,
            }
        )

    wins = [trade for trade in trades if safe_float(trade.get("pnl")) > 0]
    metrics = {
        "roi_pct": round(((equity / initial_equity) - 1) * 100, 4),
        "max_drawdown_pct": max_drawdown_pct(equity_curve),
        "total_trades": len(trades),
        "win_rate_pct": round((len(wins) / len(trades)) * 100, 4) if trades else 0.0,
        "profit_factor": profit_factor(trades),
        "fee_pct": fee_pct,
        "slippage_pct": slippage_pct,
        "max_position_pct": max_position_pct,
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
        "trades": trades,
        "equity_curve": equity_curve,
    }
