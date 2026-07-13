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


def _numeric(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def evaluate_strategy(contract: dict, features: dict) -> dict:
    strategy = contract.get("normalized_strategy") or {}
    traces = {}
    outcomes = {}
    for section in ("entry", "exit"):
        traces[section] = []
        for rule in strategy.get(section) or []:
            field = rule["field"]
            actual = features.get(field)
            expected = rule["value"]
            comparable = _numeric(actual)
            passed = comparable is not None and OPERATORS[rule["operator"]](comparable, float(expected))
            traces[section].append({**rule, "actual": actual, "passed": passed})
        outcomes[section] = bool(traces[section]) and all(item["passed"] for item in traces[section])

    conflict = outcomes["entry"] and outcomes["exit"]
    signal = "hold" if conflict else "entry_candidate" if outcomes["entry"] else "exit_candidate" if outcomes["exit"] else "hold"
    return {
        "signal": signal,
        "entry_passed": outcomes["entry"],
        "exit_passed": outcomes["exit"],
        "conflict": conflict,
        "trace": traces,
        "execution_intent_created": False,
    }


def evaluate_position_protection(allocation: dict | None, mark_price: float, risk: dict) -> dict:
    if not allocation or float(allocation.get("quantity") or 0) <= 0:
        return {"trigger_reason": None, "position_return_pct": None}
    average_price = float(allocation["average_price"])
    position_return_pct = ((float(mark_price) / average_price) - 1) * 100
    stop_loss_pct = float(risk["stop_loss_pct"])
    take_profit_pct = float(risk["take_profit_pct"])
    trigger_reason = "stop_loss" if position_return_pct <= -stop_loss_pct else "take_profit" if position_return_pct >= take_profit_pct else None
    return {
        "trigger_reason": trigger_reason,
        "position_return_pct": position_return_pct,
        "trace": {
            "average_price": average_price,
            "mark_price": float(mark_price),
            "return_pct": round(position_return_pct, 6),
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "passed": bool(trigger_reason),
        },
    }
