from __future__ import annotations

import calendar
import json
from datetime import datetime, timedelta, timezone

from backend.app.storage.spot_portfolio import (
    DEFAULT_PORTFOLIO_ID,
    FEE_RATE,
    execute_spot_transaction,
    latest_mark,
    portfolio_snapshot,
    quote_spot_transaction,
)
from backend.app.storage.sqlite import connect, initialize_database


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return utc_now()
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def advance_schedule(value: datetime, frequency: str, interval_count: int) -> datetime:
    if frequency == "weekly":
        return value + timedelta(weeks=interval_count)
    month_index = value.month - 1 + interval_count
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _validate_plan(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    symbol = str(payload.get("symbol") or "").strip().upper()
    frequency = str(payload.get("frequency") or "").strip().lower()
    budget_amount = float(payload.get("budget_amount") or 0)
    interval_count = int(payload.get("interval_count") or 1)
    allocation_limit_pct = float(payload.get("allocation_limit_pct") or 0)
    if len(name) < 3 or len(name) > 100:
        raise ValueError("DCA plan name must contain 3 to 100 characters")
    if len(symbol) < 3 or len(symbol) > 30:
        raise ValueError("Invalid DCA symbol")
    if frequency not in {"weekly", "monthly"}:
        raise ValueError("DCA frequency must be weekly or monthly")
    if budget_amount < 1 or budget_amount > 10_000_000:
        raise ValueError("DCA budget must be between 1 and 10,000,000")
    if interval_count < 1 or interval_count > 52:
        raise ValueError("DCA interval count must be between 1 and 52")
    if allocation_limit_pct <= 0 or allocation_limit_pct > 100:
        raise ValueError("DCA allocation limit must be greater than 0 and at most 100")
    return {
        "name": name,
        "symbol": symbol,
        "frequency": frequency,
        "budget_amount": budget_amount,
        "interval_count": interval_count,
        "allocation_limit_pct": allocation_limit_pct,
        "next_run_at": iso(parse_datetime(payload.get("next_run_at"))),
    }


def _get_plan(connection, plan_id: int) -> dict:
    row = connection.execute("SELECT * FROM spot_dca_plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        raise ValueError("DCA plan not found")
    return dict(row)


def _decorate_plan(plan: dict, now: datetime | None = None) -> dict:
    current = now or utc_now()
    plan["due"] = plan["status"] == "active" and parse_datetime(plan["next_run_at"]) <= current
    plan["execution_mode"] = "manual_due_run"
    plan["live_execution"] = "blocked"
    return plan


def create_dca_plan(payload: dict, portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    normalized = _validate_plan(payload)
    portfolio_snapshot(portfolio_id)
    now = iso(utc_now())
    with connect() as connection:
        latest_mark(connection, normalized["symbol"])
        plan_id = int(connection.execute(
            """INSERT INTO spot_dca_plans
            (portfolio_id, name, symbol, budget_amount, frequency, interval_count,
             allocation_limit_pct, status, next_run_at, last_run_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, NULL, ?, ?)""",
            (
                portfolio_id, normalized["name"], normalized["symbol"], normalized["budget_amount"],
                normalized["frequency"], normalized["interval_count"], normalized["allocation_limit_pct"],
                normalized["next_run_at"], now, now,
            ),
        ).lastrowid)
        plan = _decorate_plan(_get_plan(connection, plan_id))
    return {"plan": plan, "preview": preview_dca_plan(plan_id), "execution_created": False}


def list_dca_plans(portfolio_id: int = DEFAULT_PORTFOLIO_ID, limit: int = 100) -> dict:
    initialize_database()
    with connect() as connection:
        plans = [
            _decorate_plan(dict(row)) for row in connection.execute(
                "SELECT * FROM spot_dca_plans WHERE portfolio_id = ? ORDER BY id DESC LIMIT ?",
                (portfolio_id, limit),
            ).fetchall()
        ]
        executions = [dict(row) for row in connection.execute(
            """SELECT * FROM spot_dca_executions WHERE portfolio_id = ?
            ORDER BY id DESC LIMIT 100""",
            (portfolio_id,),
        ).fetchall()]
    return {
        "plans": plans,
        "executions": executions,
        "due_count": sum(1 for plan in plans if plan["due"]),
        "mode": "spot_dca_manual_execution",
        "scheduler": "not_running",
        "live_execution": "blocked",
    }


def set_dca_plan_status(plan_id: int, status: str) -> dict:
    initialize_database()
    status = str(status).strip().lower()
    if status not in {"active", "paused", "archived"}:
        raise ValueError("Invalid DCA plan status")
    with connect() as connection:
        plan = _get_plan(connection, plan_id)
        if plan["status"] == "archived" and status != "archived":
            raise ValueError("Archived DCA plans cannot be reactivated")
        connection.execute(
            "UPDATE spot_dca_plans SET status = ?, updated_at = ? WHERE id = ?",
            (status, iso(utc_now()), plan_id),
        )
        updated = _decorate_plan(_get_plan(connection, plan_id))
    return {"plan": updated, "execution_created": False}


def preview_dca_plan(plan_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        plan = _decorate_plan(_get_plan(connection, plan_id))
        mark = latest_mark(connection, plan["symbol"])
    snapshot = portfolio_snapshot(plan["portfolio_id"])
    quantity = float(plan["budget_amount"]) / (mark["price"] * (1 + FEE_RATE))
    quote = quote_spot_transaction(
        {"symbol": plan["symbol"], "side": "buy", "quantity": quantity},
        portfolio_id=plan["portfolio_id"],
    )
    holding = next((item for item in snapshot["holdings"] if item["symbol"] == plan["symbol"]), None)
    current_symbol_value = float(holding["market_value"]) if holding else 0.0
    projected_equity = max(float(snapshot["equity"]) - float(quote["fee"]), 0.0)
    projected_weight = (
        (current_symbol_value + float(quote["notional"])) / projected_equity * 100
        if projected_equity else 100.0
    )
    allocation_allowed = projected_weight <= float(plan["allocation_limit_pct"]) + 1e-9
    allowed = bool(quote["allowed"] and allocation_allowed and plan["status"] == "active")
    reason = None
    if plan["status"] != "active":
        reason = f"Plan is {plan['status']}"
    elif not quote["allowed"]:
        reason = quote["rejection_reason"]
    elif not allocation_allowed:
        reason = f"Projected {plan['symbol']} allocation {projected_weight:.2f}% exceeds {float(plan['allocation_limit_pct']):.2f}% limit"
    return {
        "plan": plan,
        "quote": quote,
        "projected_weight_pct": projected_weight,
        "allocation_limit_pct": float(plan["allocation_limit_pct"]),
        "allocation_allowed": allocation_allowed,
        "allowed": allowed,
        "reason": reason,
        "due": plan["due"],
        "execution_created": False,
    }


def _save_rejection(plan: dict, scheduled_for: str, preview: dict, reason: str) -> dict:
    now = iso(utc_now())
    snapshot = portfolio_snapshot(plan["portfolio_id"])
    with connect() as connection:
        connection.execute(
            """INSERT INTO spot_dca_executions
            (plan_id, portfolio_id, cycle_number, scheduled_for, status, transaction_id,
             quantity, price, notional, reason, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'rejected', NULL, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id, scheduled_for) DO UPDATE SET status='rejected', reason=excluded.reason,
            quantity=excluded.quantity, price=excluded.price, notional=excluded.notional,
            payload_json=excluded.payload_json, updated_at=excluded.updated_at""",
            (
                plan["id"], plan["portfolio_id"], int(snapshot["portfolio"]["active_cycle"]), scheduled_for,
                preview["quote"]["quantity"], preview["quote"]["price"], preview["quote"]["notional"], reason,
                json.dumps({"projected_weight_pct": preview["projected_weight_pct"], "allocation_limit_pct": preview["allocation_limit_pct"]}, sort_keys=True),
                now, now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM spot_dca_executions WHERE plan_id = ? AND scheduled_for = ?",
            (plan["id"], scheduled_for),
        ).fetchone()
    return dict(row)


def _finalize_dca_execution(plan: dict, scheduled_for: str, transaction: dict, recovered: bool) -> dict:
    plan_id = int(plan["id"])
    origin_reference = f"dca:{plan_id}:{scheduled_for}"
    next_run = advance_schedule(parse_datetime(scheduled_for), plan["frequency"], int(plan["interval_count"]))
    now = iso(utc_now())
    with connect() as connection:
        current_portfolio = connection.execute(
            "SELECT active_cycle FROM spot_portfolios WHERE id = ?", (plan["portfolio_id"],)
        ).fetchone()
        connection.execute(
            """INSERT INTO spot_dca_executions
            (plan_id, portfolio_id, cycle_number, scheduled_for, status, transaction_id,
             quantity, price, notional, reason, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'executed', ?, ?, ?, ?, NULL, ?, ?, ?)
            ON CONFLICT(plan_id, scheduled_for) DO UPDATE SET status='executed',
            transaction_id=excluded.transaction_id, quantity=excluded.quantity, price=excluded.price,
            notional=excluded.notional, reason=NULL, payload_json=excluded.payload_json,
            updated_at=excluded.updated_at""",
            (
                plan_id, plan["portfolio_id"], int(current_portfolio["active_cycle"]), scheduled_for,
                transaction["id"], transaction["quantity"], transaction["price"], transaction["notional"],
                json.dumps({"origin_reference": origin_reference, "recovered_transaction": recovered}, sort_keys=True),
                now, now,
            ),
        )
        connection.execute(
            "UPDATE spot_dca_plans SET last_run_at = ?, next_run_at = ?, updated_at = ? WHERE id = ?",
            (now, iso(next_run), now, plan_id),
        )
        execution = dict(connection.execute(
            "SELECT * FROM spot_dca_executions WHERE plan_id = ? AND scheduled_for = ?",
            (plan_id, scheduled_for),
        ).fetchone())
        updated_plan = _decorate_plan(_get_plan(connection, plan_id))
    return {
        "status": "executed",
        "execution": execution,
        "plan": updated_plan,
        "transaction": transaction,
        "recovered_transaction": recovered,
        "snapshot": portfolio_snapshot(plan["portfolio_id"]),
        "live_execution": "blocked",
    }


def execute_due_dca_plan(plan_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        plan = _decorate_plan(_get_plan(connection, plan_id))
    if plan["status"] != "active":
        raise ValueError(f"DCA plan is {plan['status']}")
    if not plan["due"]:
        raise ValueError("DCA plan is not due yet")
    scheduled_for = plan["next_run_at"]
    origin_reference = f"dca:{plan_id}:{scheduled_for}"
    with connect() as connection:
        recovered_row = connection.execute(
            """SELECT * FROM spot_transactions
            WHERE portfolio_id = ? AND origin = 'dca_plan' AND origin_reference = ?""",
            (plan["portfolio_id"], origin_reference),
        ).fetchone()
    if recovered_row:
        return _finalize_dca_execution(plan, scheduled_for, dict(recovered_row), recovered=True)

    preview = preview_dca_plan(plan_id)
    if not preview["allowed"]:
        execution = _save_rejection(plan, scheduled_for, preview, str(preview["reason"]))
        return {"status": "rejected", "execution": execution, "preview": preview, "plan": plan, "snapshot": portfolio_snapshot(plan["portfolio_id"])}

    result = execute_spot_transaction(
        {
            "symbol": plan["symbol"],
            "side": "buy",
            "quantity": preview["quote"]["quantity"],
            "notes": f"DCA plan #{plan_id} · {plan['name']}",
            "origin": "dca_plan",
            "origin_reference": origin_reference,
        },
        portfolio_id=plan["portfolio_id"],
    )
    return _finalize_dca_execution(plan, scheduled_for, result["transaction"], recovered=result["recovered"])
