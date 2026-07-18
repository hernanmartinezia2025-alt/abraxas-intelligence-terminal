from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from backend.app.analytics.spot_risk import build_spot_risk_context
from backend.app.storage.risk import validate_order_intent
from backend.app.storage.spot_portfolio import (
    DEFAULT_PORTFOLIO_ID,
    FEE_RATE,
    execute_spot_transaction,
    get_spot_transaction_by_origin,
    latest_mark,
    portfolio_snapshot,
)
from backend.app.storage.sqlite import connect, initialize_database


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_policy(name: str, targets: list[dict], min_trade_notional: float) -> dict:
    clean_name = str(name or "").strip()
    if len(clean_name) < 3 or len(clean_name) > 100:
        raise ValueError("Allocation policy name must contain 3 to 100 characters")
    minimum = float(min_trade_notional)
    if minimum < 1 or minimum > 1_000_000:
        raise ValueError("Minimum trade notional must be between 1 and 1,000,000")
    if not isinstance(targets, list) or not targets or len(targets) > 50:
        raise ValueError("Allocation policy requires 1 to 50 targets")
    normalized = []
    seen: set[str] = set()
    for raw in targets:
        symbol = str(raw.get("symbol") or "").strip().upper()
        target_pct = float(raw.get("target_pct") or 0)
        if len(symbol) < 3 or len(symbol) > 30:
            raise ValueError("Invalid allocation target symbol")
        if symbol in seen:
            raise ValueError(f"Duplicate allocation target: {symbol}")
        if target_pct <= 0 or target_pct > 100:
            raise ValueError(f"Target for {symbol} must be greater than 0 and at most 100")
        seen.add(symbol)
        normalized.append({"symbol": symbol, "target_pct": round(target_pct, 6)})
    normalized.sort(key=lambda item: item["symbol"])
    target_total = sum(item["target_pct"] for item in normalized)
    if target_total > 100 + 1e-9:
        raise ValueError("Allocation targets cannot exceed 100%")
    config = {
        "targets": normalized,
        "min_trade_notional": minimum,
        "cash_target_pct": round(100 - target_total, 6),
    }
    config_hash = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"name": clean_name, **config, "config_hash": config_hash}


def _policy_detail(connection, policy_id: int) -> dict:
    policy_row = connection.execute("SELECT * FROM spot_allocation_policies WHERE id = ?", (policy_id,)).fetchone()
    if not policy_row:
        raise ValueError("Allocation policy not found")
    policy = dict(policy_row)
    version_row = connection.execute(
        """SELECT * FROM spot_allocation_policy_versions
        WHERE policy_id = ? AND version_number = ?""",
        (policy_id, policy["active_version"]),
    ).fetchone()
    if not version_row:
        raise ValueError("Active allocation policy version not found")
    version = dict(version_row)
    version["targets"] = json.loads(version.pop("targets_json"))
    policy["active_config"] = version
    return policy


def save_allocation_policy(
    name: str,
    targets: list[dict],
    min_trade_notional: float = 25,
    portfolio_id: int = DEFAULT_PORTFOLIO_ID,
) -> dict:
    initialize_database()
    normalized = _normalize_policy(name, targets, min_trade_notional)
    portfolio_snapshot(portfolio_id)
    now = now_iso()
    with connect() as connection:
        for target in normalized["targets"]:
            latest_mark(connection, target["symbol"])
        existing = connection.execute(
            "SELECT * FROM spot_allocation_policies WHERE portfolio_id = ? AND name = ?",
            (portfolio_id, normalized["name"]),
        ).fetchone()
        if existing:
            policy_id = int(existing["id"])
            same = connection.execute(
                "SELECT version_number FROM spot_allocation_policy_versions WHERE policy_id = ? AND config_hash = ?",
                (policy_id, normalized["config_hash"]),
            ).fetchone()
            if same:
                version_number = int(same["version_number"])
            else:
                version_number = int(connection.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM spot_allocation_policy_versions WHERE policy_id = ?",
                    (policy_id,),
                ).fetchone()[0])
                connection.execute(
                    """INSERT INTO spot_allocation_policy_versions
                    (policy_id, version_number, targets_json, min_trade_notional, config_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        policy_id, version_number, json.dumps(normalized["targets"], sort_keys=True),
                        normalized["min_trade_notional"], normalized["config_hash"], now,
                    ),
                )
            connection.execute(
                "UPDATE spot_allocation_policies SET status='active', active_version=?, updated_at=? WHERE id=?",
                (version_number, now, policy_id),
            )
        else:
            policy_id = int(connection.execute(
                """INSERT INTO spot_allocation_policies
                (portfolio_id, name, status, active_version, created_at, updated_at)
                VALUES (?, ?, 'active', 1, ?, ?)""",
                (portfolio_id, normalized["name"], now, now),
            ).lastrowid)
            connection.execute(
                """INSERT INTO spot_allocation_policy_versions
                (policy_id, version_number, targets_json, min_trade_notional, config_hash, created_at)
                VALUES (?, 1, ?, ?, ?, ?)""",
                (policy_id, json.dumps(normalized["targets"], sort_keys=True), normalized["min_trade_notional"], normalized["config_hash"], now),
            )
        detail = _policy_detail(connection, policy_id)
    return {"policy": detail, "execution_created": False, "live_execution": "blocked"}


def list_allocation_policies(portfolio_id: int = DEFAULT_PORTFOLIO_ID, limit: int = 100) -> dict:
    initialize_database()
    with connect() as connection:
        policy_ids = [int(row["id"]) for row in connection.execute(
            "SELECT id FROM spot_allocation_policies WHERE portfolio_id = ? ORDER BY id DESC LIMIT ?",
            (portfolio_id, limit),
        ).fetchall()]
        policies = [_policy_detail(connection, policy_id) for policy_id in policy_ids]
        run_rows = connection.execute(
            "SELECT * FROM spot_rebalance_runs WHERE portfolio_id = ? ORDER BY id DESC LIMIT 50",
            (portfolio_id,),
        ).fetchall()
        runs = [_decode_run(dict(row)) for row in run_rows]
    return {"policies": policies, "runs": runs, "mode": "spot_rebalance_simulation", "live_execution": "blocked"}


def archive_allocation_policy(policy_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        _policy_detail(connection, policy_id)
        connection.execute(
            "UPDATE spot_allocation_policies SET status='archived', updated_at=? WHERE id=?",
            (now_iso(), policy_id),
        )
        detail = _policy_detail(connection, policy_id)
    return {"policy": detail, "execution_created": False}


def _portfolio_state_hash(snapshot: dict) -> str:
    payload = {
        "cycle": int(snapshot["portfolio"]["active_cycle"]),
        "cash": round(float(snapshot["portfolio"]["cash_balance"]), 8),
        "holdings": [
            {
                "symbol": item["symbol"],
                "quantity": round(float(item["quantity"]), 12),
                "average_cost": round(float(item["average_cost"]), 12),
            }
            for item in sorted(snapshot["holdings"], key=lambda row: row["symbol"])
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _build_rebalance_plan(policy: dict, snapshot: dict) -> tuple[list[dict], dict]:
    config = policy["active_config"]
    targets = {item["symbol"]: float(item["target_pct"]) for item in config["targets"]}
    holdings = {item["symbol"]: item for item in snapshot["holdings"]}
    symbols = sorted(set(targets) | set(holdings))
    equity = float(snapshot["equity"])
    minimum = float(config["min_trade_notional"])
    raw_sells: list[dict] = []
    raw_buys: list[dict] = []
    current_weights: dict[str, float] = {}
    target_weights = {**targets, "CASH": max(0.0, 100 - sum(targets.values()))}
    with connect() as connection:
        for symbol in symbols:
            mark = latest_mark(connection, symbol)
            holding = holdings.get(symbol)
            current_value = float(holding["quantity"]) * mark["price"] if holding else 0.0
            current_weights[symbol] = current_value / equity * 100 if equity else 0.0
            target_value = equity * targets.get(symbol, 0.0) / 100
            delta = target_value - current_value
            if abs(delta) + 1e-9 < minimum:
                continue
            if delta < 0 and holding:
                notional = min(current_value, abs(delta))
                raw_sells.append({
                    "symbol": symbol, "side": "sell", "planned_notional": notional,
                    "planned_quantity": min(float(holding["quantity"]), notional / mark["price"]),
                    "reference_price": mark["price"], "price_timestamp": mark["timestamp"],
                })
            elif delta > 0:
                raw_buys.append({
                    "symbol": symbol, "side": "buy", "planned_notional": delta,
                    "planned_quantity": delta / mark["price"], "reference_price": mark["price"],
                    "price_timestamp": mark["timestamp"],
                })
    current_weights["CASH"] = float(snapshot["portfolio"]["cash_balance"]) / equity * 100 if equity else 0.0
    sell_cash = sum(order["planned_notional"] * (1 - FEE_RATE) for order in raw_sells)
    cash_target_value = equity * target_weights["CASH"] / 100
    available_buy_cash = max(0.0, float(snapshot["portfolio"]["cash_balance"]) + sell_cash - cash_target_value)
    requested_buy_cash = sum(order["planned_notional"] * (1 + FEE_RATE) for order in raw_buys)
    buy_scale = min(1.0, available_buy_cash / requested_buy_cash) if requested_buy_cash else 1.0
    buys = []
    for order in raw_buys:
        notional = order["planned_notional"] * buy_scale
        if notional + 1e-9 < minimum:
            continue
        buys.append({**order, "planned_notional": notional, "planned_quantity": notional / order["reference_price"]})
    orders = raw_sells + buys
    for index, order in enumerate(orders, start=1):
        order["order_index"] = index
        order["estimated_fee"] = order["planned_notional"] * FEE_RATE
    expected_values = {symbol: (float(holdings[symbol]["market_value"]) if symbol in holdings else 0.0) for symbol in symbols}
    expected_cash = float(snapshot["portfolio"]["cash_balance"])
    for order in orders:
        direction = 1 if order["side"] == "buy" else -1
        expected_values[order["symbol"]] = expected_values.get(order["symbol"], 0.0) + direction * order["planned_notional"]
        expected_cash += -order["planned_notional"] - order["estimated_fee"] if order["side"] == "buy" else order["planned_notional"] - order["estimated_fee"]
    expected_equity = expected_cash + sum(expected_values.values())
    expected_weights = {symbol: max(0.0, value) / expected_equity * 100 if expected_equity else 0.0 for symbol, value in expected_values.items()}
    expected_weights["CASH"] = expected_cash / expected_equity * 100 if expected_equity else 0.0
    measured_symbols = set(target_weights) | set(current_weights) | set(expected_weights)
    current_drift = sum(
        abs(current_weights.get(symbol, 0.0) - target_weights.get(symbol, 0.0))
        for symbol in measured_symbols
    )
    expected_drift = sum(
        abs(expected_weights.get(symbol, 0.0) - target_weights.get(symbol, 0.0))
        for symbol in measured_symbols
    )
    metrics = {
        "target_weights": target_weights,
        "current_weights": current_weights,
        "expected_weights": expected_weights,
        "current_drift_pct_points": current_drift,
        "expected_drift_pct_points": expected_drift,
        "buy_scale": buy_scale,
        "estimated_fees": sum(order["estimated_fee"] for order in orders),
        "cash_target_value": cash_target_value,
        "orders_total": len(orders),
        "concentration_hhi": sum(weight * weight for key, weight in current_weights.items() if key != "CASH") / 10_000,
    }
    return orders, metrics


def _decode_run(run: dict) -> dict:
    run["plan"] = json.loads(run.pop("plan_json"))
    run["metrics"] = json.loads(run.pop("metrics_json"))
    execution_json = run.pop("execution_json", None)
    run["execution"] = json.loads(execution_json) if execution_json else []
    return run


def _risk_payload(order: dict, snapshot: dict, *, source: str, run_id: int | None = None) -> dict:
    context = build_spot_risk_context(snapshot)
    holding = next((item for item in snapshot["holdings"] if item["symbol"] == order["symbol"]), None)
    return {
        "mode": "spot",
        "symbol": order["symbol"],
        "side": "long",
        "requested_notional": float(order["planned_notional"]),
        "current_exposure_notional": float(holding["market_value"]) if holding else 0.0,
        "account_equity": context["account_equity"],
        "daily_pnl": context["daily_pnl"],
        "current_drawdown_pct": context["current_drawdown_pct"],
        "last_loss_at": context["last_loss_at"],
        "reduces_exposure": order["side"] == "sell",
        "source": source,
        "rebalance_run_id": run_id,
        "order_index": order["order_index"],
        "risk_data_coverage": context["coverage"],
        "risk_observed_since": context["observed_since"],
    }


def create_rebalance_run(policy_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        policy = _policy_detail(connection, policy_id)
    if policy["status"] != "active":
        raise ValueError("Archived allocation policy cannot create a rebalance run")
    snapshot = portfolio_snapshot(policy["portfolio_id"])
    orders, metrics = _build_rebalance_plan(policy, snapshot)
    risk_preview = []
    projected_exposure = {item["symbol"]: float(item["market_value"]) for item in snapshot["holdings"]}
    for order in orders:
        payload = _risk_payload(order, snapshot, source="spot_rebalance_preview")
        payload["current_exposure_notional"] = projected_exposure.get(order["symbol"], 0.0)
        decision = validate_order_intent(payload, persist=False)
        risk_preview.append({"order_index": order["order_index"], "symbol": order["symbol"], "side": order["side"], **decision})
        direction = -1 if order["side"] == "sell" else 1
        projected_exposure[order["symbol"]] = max(
            0.0,
            projected_exposure.get(order["symbol"], 0.0) + direction * float(order["planned_notional"]),
        )
    metrics["risk_preview"] = risk_preview
    metrics["risk_ready"] = all(item["approved"] for item in risk_preview)
    metrics["risk_gate"] = "mandatory_on_apply"
    now = now_iso()
    with connect() as connection:
        run_id = int(connection.execute(
            """INSERT INTO spot_rebalance_runs
            (portfolio_id, policy_id, policy_version_id, status, portfolio_state_hash,
             equity_at_plan, cash_at_plan, source_timestamp, plan_json, metrics_json,
             execution_json, created_at, applied_at, updated_at)
            VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, NULL, ?, NULL, ?)""",
            (
                policy["portfolio_id"], policy_id, policy["active_config"]["id"], _portfolio_state_hash(snapshot),
                snapshot["equity"], snapshot["portfolio"]["cash_balance"], snapshot["valuation_source_timestamp"],
                json.dumps(orders, sort_keys=True), json.dumps(metrics, sort_keys=True), now, now,
            ),
        ).lastrowid)
        run = _decode_run(dict(connection.execute("SELECT * FROM spot_rebalance_runs WHERE id = ?", (run_id,)).fetchone()))
    return {"run": run, "policy": policy, "snapshot": snapshot, "execution_created": False, "live_execution": "blocked"}


def apply_rebalance_run(run_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        row = connection.execute("SELECT * FROM spot_rebalance_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise ValueError("Rebalance run not found")
    run = _decode_run(dict(row))
    if run["status"] == "applied":
        return {"run": run, "snapshot": portfolio_snapshot(run["portfolio_id"]), "recovered": True, "live_execution": "blocked"}
    if run["status"] == "draft":
        current_snapshot = portfolio_snapshot(run["portfolio_id"])
        if _portfolio_state_hash(current_snapshot) != run["portfolio_state_hash"]:
            raise ValueError("Portfolio state changed after preview; create a new rebalance run")
        with connect() as connection:
            connection.execute(
                "UPDATE spot_rebalance_runs SET status='applying', updated_at=? WHERE id=? AND status='draft'",
                (now_iso(), run_id),
            )
        run["status"] = "applying"
    results = []
    for order in sorted(run["plan"], key=lambda item: (0 if item["side"] == "sell" else 1, item["order_index"])):
        reference = f"rebalance:{run_id}:{order['order_index']}:{order['symbol']}"
        existing = get_spot_transaction_by_origin("rebalance_run", reference, run["portfolio_id"])
        if existing:
            results.append({
                "order_index": order["order_index"], "symbol": order["symbol"], "side": order["side"],
                "status": "executed", "transaction_id": existing["id"], "recovered": True,
                "risk_validation_id": existing.get("risk_validation_id"),
            })
            continue
        current_snapshot = portfolio_snapshot(run["portfolio_id"])
        risk = validate_order_intent(
            _risk_payload(order, current_snapshot, source="spot_rebalance_apply", run_id=run_id)
        )
        if not risk["approved"]:
            results.append({
                "order_index": order["order_index"], "symbol": order["symbol"], "side": order["side"],
                "status": "rejected", "stage": "risk", "reason": " · ".join(risk["reasons"]),
                "risk_validation_id": risk["validation_id"], "risk_checks": risk["checks"],
            })
            with connect() as connection:
                connection.execute(
                    "UPDATE spot_rebalance_runs SET execution_json=?, updated_at=? WHERE id=?",
                    (json.dumps(results, sort_keys=True), now_iso(), run_id),
                )
            continue
        try:
            result = execute_spot_transaction(
                {
                    "symbol": order["symbol"], "side": order["side"], "quantity": order["planned_quantity"],
                    "notes": f"Rebalance run #{run_id}", "origin": "rebalance_run", "origin_reference": reference,
                    "risk_validation_id": risk["validation_id"],
                },
                portfolio_id=run["portfolio_id"],
            )
            results.append({
                "order_index": order["order_index"], "symbol": order["symbol"], "side": order["side"],
                "status": "executed", "transaction_id": result["transaction_id"], "recovered": result["recovered"],
                "risk_validation_id": risk["validation_id"],
            })
        except ValueError as exc:
            results.append({
                "order_index": order["order_index"], "symbol": order["symbol"], "side": order["side"],
                "status": "rejected", "stage": "execution", "reason": str(exc),
                "risk_validation_id": risk["validation_id"],
            })
        with connect() as connection:
            connection.execute(
                "UPDATE spot_rebalance_runs SET execution_json=?, updated_at=? WHERE id=?",
                (json.dumps(results, sort_keys=True), now_iso(), run_id),
            )
    complete = all(item["status"] == "executed" for item in results) and len(results) == len(run["plan"])
    status = "applied" if complete else "partial"
    now = now_iso()
    with connect() as connection:
        connection.execute(
            """UPDATE spot_rebalance_runs SET status=?, execution_json=?, applied_at=?, updated_at=? WHERE id=?""",
            (status, json.dumps(results, sort_keys=True), now if complete else None, now, run_id),
        )
        final_run = _decode_run(dict(connection.execute("SELECT * FROM spot_rebalance_runs WHERE id = ?", (run_id,)).fetchone()))
    return {
        "run": final_run,
        "snapshot": portfolio_snapshot(run["portfolio_id"]),
        "recovered": False,
        "live_execution": "blocked",
    }
