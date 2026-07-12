from __future__ import annotations

import hashlib
import json


CONTRACT_VERSION = "1.0"
SUPPORTED_ENGINE = "rules"
SUPPORTED_OPERATORS = {">", ">=", "<", "<=", "==", "!="}
RISK_DEFAULTS = {"max_position_pct": 10.0, "stop_loss_pct": 2.0, "take_profit_pct": 4.0}


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc


def _rules(value: object, section: str) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"strategy.{section} must contain at least one rule")
    normalized = []
    for index, rule in enumerate(value, start=1):
        if not isinstance(rule, dict):
            raise ValueError(f"strategy.{section}[{index}] must be an object")
        field = str(rule.get("field") or "").strip()
        operator = str(rule.get("operator") or "").strip()
        if not field:
            raise ValueError(f"strategy.{section}[{index}].field is required")
        if operator not in SUPPORTED_OPERATORS:
            raise ValueError(f"strategy.{section}[{index}].operator is not supported")
        normalized.append({"field": field, "operator": operator, "value": _number(rule.get("value"), f"strategy.{section}[{index}].value")})
    return normalized


def compile_strategy(strategy: object) -> dict:
    if not isinstance(strategy, dict):
        raise ValueError("strategy must be a JSON object")
    engine = str(strategy.get("engine") or SUPPORTED_ENGINE).strip().lower()
    if engine != SUPPORTED_ENGINE:
        raise ValueError(f"Unsupported strategy engine: {engine}")
    risk_input = strategy.get("risk") or {}
    if not isinstance(risk_input, dict):
        raise ValueError("strategy.risk must be an object")
    risk = {key: _number(risk_input.get(key, default), f"strategy.risk.{key}") for key, default in RISK_DEFAULTS.items()}
    if not 0 < risk["max_position_pct"] <= 100:
        raise ValueError("strategy.risk.max_position_pct must be greater than 0 and at most 100")
    if risk["stop_loss_pct"] <= 0 or risk["take_profit_pct"] <= 0:
        raise ValueError("strategy stop loss and take profit must be greater than 0")

    normalized = {
        "engine": engine,
        "entry": _rules(strategy.get("entry"), "entry"),
        "exit": _rules(strategy.get("exit"), "exit"),
        "risk": risk,
    }
    canonical = json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    fields = sorted({rule["field"] for section in ("entry", "exit") for rule in normalized[section]})
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "valid",
        "engine": engine,
        "strategy_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "required_fields": fields,
        "capabilities": {"backtest": True, "paper": False, "live": False},
        "execution_model": "signal_close_fill_next_open",
        "position_mode": "long_only",
        "normalized_strategy": normalized,
    }
