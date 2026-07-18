from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database

DEFAULT_PORTFOLIO_ID = 1
DEFAULT_CASH = 10_000.0
FEE_RATE = 0.001


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_portfolio(connection) -> None:
    now = now_iso()
    connection.execute(
        """INSERT OR IGNORE INTO spot_portfolios
        (id, name, base_currency, initial_cash, cash_balance, active_cycle, created_at, updated_at)
        VALUES (?, 'ABRAXAS Spot Long Term', 'USDT', ?, ?, 1, ?, ?)""",
        (DEFAULT_PORTFOLIO_ID, DEFAULT_CASH, DEFAULT_CASH, now, now),
    )


def latest_mark(connection, symbol: str) -> dict:
    row = connection.execute(
        "SELECT price, timestamp FROM market_snapshots WHERE symbol = ? ORDER BY timestamp DESC, id DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    if not row:
        raise ValueError(f"No persisted market price is available for {symbol}")
    return {"price": float(row["price"]), "timestamp": row["timestamp"]}


def _portfolio_row(connection, portfolio_id: int) -> dict:
    seed_portfolio(connection)
    row = connection.execute("SELECT * FROM spot_portfolios WHERE id = ?", (portfolio_id,)).fetchone()
    if not row:
        raise ValueError("Spot portfolio not found")
    return dict(row)


def _valuation_metrics(connection, portfolio: dict) -> dict:
    holdings = [dict(row) for row in connection.execute(
        "SELECT * FROM spot_holdings WHERE portfolio_id = ? AND quantity > 0 ORDER BY symbol",
        (portfolio["id"],),
    ).fetchall()]
    market_value = 0.0
    cost_basis = 0.0
    unrealized_pnl = 0.0
    source_timestamps: list[str] = []
    fingerprint_holdings: list[dict] = []
    for holding in holdings:
        mark = latest_mark(connection, holding["symbol"])
        holding["market_price"] = mark["price"]
        holding["price_timestamp"] = mark["timestamp"]
        holding["market_value"] = float(holding["quantity"]) * mark["price"]
        holding["cost_basis"] = float(holding["quantity"]) * float(holding["average_cost"])
        holding["unrealized_pnl"] = holding["market_value"] - holding["cost_basis"]
        holding["return_pct"] = holding["unrealized_pnl"] / holding["cost_basis"] * 100 if holding["cost_basis"] else 0.0
        market_value += holding["market_value"]
        cost_basis += holding["cost_basis"]
        unrealized_pnl += holding["unrealized_pnl"]
        source_timestamps.append(str(mark["timestamp"]))
        fingerprint_holdings.append({
            "symbol": holding["symbol"],
            "quantity": round(float(holding["quantity"]), 12),
            "price": round(mark["price"], 12),
            "price_timestamp": mark["timestamp"],
        })
    equity = float(portfolio["cash_balance"]) + market_value
    for holding in holdings:
        holding["weight_pct"] = holding["market_value"] / equity * 100 if equity else 0.0
    realized_pnl = float(connection.execute(
        "SELECT COALESCE(SUM(realized_pnl), 0) FROM spot_holdings WHERE portfolio_id = ?",
        (portfolio["id"],),
    ).fetchone()[0])
    cycle = int(portfolio.get("active_cycle") or 1)
    cash_flows_total = float(connection.execute(
        "SELECT COALESCE(SUM(cash_delta), 0) FROM spot_cash_flows WHERE portfolio_id = ? AND cycle_number = ?",
        (portfolio["id"], cycle),
    ).fetchone()[0])
    net_contributions = float(portfolio["initial_cash"]) + cash_flows_total
    total_pnl = equity - net_contributions
    fingerprint_payload = {
        "cycle": cycle,
        "cash": round(float(portfolio["cash_balance"]), 8),
        "holdings": fingerprint_holdings,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "holdings": holdings,
        "market_value": market_value,
        "cost_basis": cost_basis,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "equity": equity,
        "net_contributions": net_contributions,
        "total_pnl": total_pnl,
        "total_return_pct": total_pnl / net_contributions * 100 if net_contributions else 0.0,
        "holdings_return_pct": unrealized_pnl / cost_basis * 100 if cost_basis else 0.0,
        "source_timestamp": max(source_timestamps) if source_timestamps else portfolio["updated_at"],
        "fingerprint": fingerprint,
    }


def _insert_ledger(
    connection,
    portfolio: dict,
    event_type: str,
    *,
    reference_id: int | None = None,
    symbol: str | None = None,
    cash_delta: float = 0.0,
    quantity_delta: float = 0.0,
    realized_pnl_delta: float = 0.0,
    payload: dict | None = None,
    created_at: str | None = None,
) -> int:
    return int(connection.execute(
        """INSERT INTO spot_portfolio_ledger
        (portfolio_id, cycle_number, event_type, reference_id, symbol, cash_delta,
         quantity_delta, realized_pnl_delta, cash_balance, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            portfolio["id"], int(portfolio.get("active_cycle") or 1), event_type, reference_id, symbol,
            cash_delta, quantity_delta, realized_pnl_delta, float(portfolio["cash_balance"]),
            json.dumps(payload or {}, sort_keys=True, ensure_ascii=True), created_at or now_iso(),
        ),
    ).lastrowid)


def _insert_equity_snapshot(connection, portfolio_id: int, reason: str) -> tuple[dict, bool]:
    portfolio = _portfolio_row(connection, portfolio_id)
    metrics = _valuation_metrics(connection, portfolio)
    recorded_at = now_iso()
    cursor = connection.execute(
        """INSERT OR IGNORE INTO spot_equity_snapshots
        (portfolio_id, cycle_number, equity, cash_balance, market_value, cost_basis,
         unrealized_pnl, realized_pnl, source_timestamp, fingerprint, reason, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            portfolio_id, int(portfolio.get("active_cycle") or 1), metrics["equity"],
            float(portfolio["cash_balance"]), metrics["market_value"], metrics["cost_basis"],
            metrics["unrealized_pnl"], metrics["realized_pnl"], metrics["source_timestamp"],
            metrics["fingerprint"], reason, recorded_at,
        ),
    )
    return metrics, cursor.rowcount > 0


def portfolio_snapshot(portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    with connect() as connection:
        portfolio = _portfolio_row(connection, portfolio_id)
        metrics = _valuation_metrics(connection, portfolio)
        cycle = int(portfolio.get("active_cycle") or 1)
        transactions = [dict(row) for row in connection.execute(
            "SELECT * FROM spot_transactions WHERE portfolio_id = ? AND cycle_number = ? ORDER BY id DESC LIMIT 100",
            (portfolio_id, cycle),
        ).fetchall()]
        cash_flows = [dict(row) for row in connection.execute(
            "SELECT * FROM spot_cash_flows WHERE portfolio_id = ? AND cycle_number = ? ORDER BY id DESC LIMIT 100",
            (portfolio_id, cycle),
        ).fetchall()]
        equity_history = [dict(row) for row in connection.execute(
            "SELECT * FROM spot_equity_snapshots WHERE portfolio_id = ? AND cycle_number = ? ORDER BY id ASC LIMIT 1000",
            (portfolio_id, cycle),
        ).fetchall()]
        ledger = [dict(row) for row in connection.execute(
            "SELECT * FROM spot_portfolio_ledger WHERE portfolio_id = ? ORDER BY id DESC LIMIT 250",
            (portfolio_id,),
        ).fetchall()]
    return {
        "portfolio": portfolio,
        "equity": metrics["equity"],
        "market_value": metrics["market_value"],
        "cost_basis": metrics["cost_basis"],
        "unrealized_pnl": metrics["unrealized_pnl"],
        "realized_pnl": metrics["realized_pnl"],
        "return_pct": metrics["holdings_return_pct"],
        "net_contributions": metrics["net_contributions"],
        "total_pnl": metrics["total_pnl"],
        "total_return_pct": metrics["total_return_pct"],
        "holdings": metrics["holdings"],
        "transactions": transactions,
        "cash_flows": cash_flows,
        "equity_history": equity_history,
        "ledger": ledger,
        "valuation_source_timestamp": metrics["source_timestamp"],
        "mode": "spot_simulation",
        "live_execution": "blocked",
    }


def _transaction_quote(connection, payload: dict, portfolio: dict) -> dict:
    symbol = str(payload["symbol"]).upper().strip()
    side = str(payload["side"]).lower().strip()
    quantity = float(payload["quantity"])
    if side not in {"buy", "sell"} or quantity <= 0:
        raise ValueError("Invalid spot transaction")
    mark = latest_mark(connection, symbol)
    price = mark["price"]
    notional = price * quantity
    fee = notional * FEE_RATE
    holding_row = connection.execute(
        "SELECT * FROM spot_holdings WHERE portfolio_id = ? AND symbol = ?", (portfolio["id"], symbol)
    ).fetchone()
    holding = dict(holding_row) if holding_row else None
    current_quantity = float(holding["quantity"]) if holding else 0.0
    average_cost = float(holding["average_cost"]) if holding else 0.0
    allowed = True
    rejection_reason = None
    realized_pnl = 0.0
    if side == "buy":
        cash_delta = -(notional + fee)
        resulting_quantity = current_quantity + quantity
        resulting_average_cost = ((current_quantity * average_cost) + notional + fee) / resulting_quantity
        if -cash_delta > float(portfolio["cash_balance"]):
            allowed = False
            rejection_reason = "Insufficient spot simulation cash"
    else:
        cash_delta = notional - fee
        resulting_quantity = current_quantity - quantity
        resulting_average_cost = average_cost if resulting_quantity > 1e-12 else 0.0
        realized_pnl = quantity * (price - average_cost) - fee
        if current_quantity + 1e-12 < quantity:
            allowed = False
            rejection_reason = "Insufficient spot holding quantity"
    return {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "price_timestamp": mark["timestamp"],
        "source": "market_snapshots",
        "notional": notional,
        "fee": fee,
        "fee_rate": FEE_RATE,
        "cash_delta": cash_delta,
        "cash_balance_before": float(portfolio["cash_balance"]),
        "cash_balance_after": float(portfolio["cash_balance"]) + cash_delta,
        "current_quantity": current_quantity,
        "resulting_quantity": resulting_quantity,
        "resulting_average_cost": resulting_average_cost,
        "realized_pnl": realized_pnl,
        "allowed": allowed,
        "rejection_reason": rejection_reason,
        "mode": "spot_simulation_quote",
        "execution_created": False,
    }


def quote_spot_transaction(payload: dict, portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    with connect() as connection:
        return _transaction_quote(connection, payload, _portfolio_row(connection, portfolio_id))


def get_spot_transaction_by_origin(
    origin: str,
    origin_reference: str,
    portfolio_id: int = DEFAULT_PORTFOLIO_ID,
) -> dict | None:
    initialize_database()
    with connect() as connection:
        row = connection.execute(
            """SELECT * FROM spot_transactions
            WHERE portfolio_id = ? AND origin = ? AND origin_reference = ?""",
            (portfolio_id, origin, origin_reference),
        ).fetchone()
    return dict(row) if row else None


def execute_spot_transaction(payload: dict, portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    now = now_iso()
    origin = str(payload.get("origin") or "manual").strip().lower()
    origin_reference = str(payload.get("origin_reference") or "").strip() or None
    if origin not in {"manual", "dca_plan", "rebalance_run"}:
        raise ValueError("Unsupported spot transaction origin")
    if origin_reference and len(origin_reference) > 200:
        raise ValueError("Spot transaction origin reference is too long")
    if origin_reference:
        with connect() as connection:
            existing = connection.execute(
                """SELECT * FROM spot_transactions
                WHERE portfolio_id = ? AND origin = ? AND origin_reference = ?""",
                (portfolio_id, origin, origin_reference),
            ).fetchone()
        if existing:
            transaction = dict(existing)
            return {
                "transaction_id": transaction["id"],
                "transaction": transaction,
                "quote": None,
                "recovered": True,
                "snapshot": portfolio_snapshot(portfolio_id),
            }
    with connect() as connection:
        portfolio = _portfolio_row(connection, portfolio_id)
        quote = _transaction_quote(connection, payload, portfolio)
        if not quote["allowed"]:
            raise ValueError(str(quote["rejection_reason"]))
        realized = float(quote["realized_pnl"])
        connection.execute(
            """INSERT INTO spot_holdings (portfolio_id, symbol, quantity, average_cost, realized_pnl, updated_at)
            VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(portfolio_id, symbol) DO UPDATE SET
            quantity=excluded.quantity, average_cost=excluded.average_cost,
            realized_pnl=spot_holdings.realized_pnl + excluded.realized_pnl, updated_at=excluded.updated_at""",
            (portfolio_id, quote["symbol"], quote["resulting_quantity"], quote["resulting_average_cost"], realized, now),
        )
        connection.execute(
            "UPDATE spot_portfolios SET cash_balance = cash_balance + ?, updated_at = ? WHERE id = ?",
            (quote["cash_delta"], now, portfolio_id),
        )
        transaction_id = int(connection.execute(
            """INSERT INTO spot_transactions
            (portfolio_id, symbol, side, quantity, price, notional, fee, realized_pnl,
             price_timestamp, source, notes, cycle_number, origin, origin_reference,
             risk_validation_id, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'market_snapshots', ?, ?, ?, ?, ?, ?)""",
            (
                portfolio_id, quote["symbol"], quote["side"], quote["quantity"], quote["price"],
                quote["notional"], quote["fee"], realized, quote["price_timestamp"],
                str(payload.get("notes") or ""), int(portfolio.get("active_cycle") or 1), origin,
                origin_reference, payload.get("risk_validation_id"), now,
            ),
        ).lastrowid)
        portfolio["cash_balance"] = quote["cash_balance_after"]
        _insert_ledger(
            connection, portfolio, "spot_transaction", reference_id=transaction_id, symbol=quote["symbol"],
            cash_delta=quote["cash_delta"], quantity_delta=quote["quantity"] if quote["side"] == "buy" else -quote["quantity"],
            realized_pnl_delta=realized, payload={"side": quote["side"], "price": quote["price"], "fee": quote["fee"], "notes": str(payload.get("notes") or ""), "origin": origin, "origin_reference": origin_reference, "risk_validation_id": payload.get("risk_validation_id")},
            created_at=now,
        )
        _insert_equity_snapshot(connection, portfolio_id, "transaction")
        transaction = dict(connection.execute("SELECT * FROM spot_transactions WHERE id = ?", (transaction_id,)).fetchone())
    return {"transaction_id": transaction_id, "transaction": transaction, "quote": quote, "recovered": False, "snapshot": portfolio_snapshot(portfolio_id)}


def apply_cash_flow(payload: dict, portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    flow_type = str(payload["flow_type"]).lower().strip()
    amount = float(payload["amount"])
    if flow_type not in {"deposit", "withdrawal"} or amount <= 0:
        raise ValueError("Invalid spot cash flow")
    now = now_iso()
    with connect() as connection:
        portfolio = _portfolio_row(connection, portfolio_id)
        cash_delta = amount if flow_type == "deposit" else -amount
        if float(portfolio["cash_balance"]) + cash_delta < -1e-9:
            raise ValueError("Insufficient cash for withdrawal")
        new_cash = float(portfolio["cash_balance"]) + cash_delta
        connection.execute(
            "UPDATE spot_portfolios SET cash_balance = ?, updated_at = ? WHERE id = ?",
            (new_cash, now, portfolio_id),
        )
        flow_id = int(connection.execute(
            """INSERT INTO spot_cash_flows
            (portfolio_id, cycle_number, flow_type, amount, cash_delta, cash_balance, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (portfolio_id, int(portfolio.get("active_cycle") or 1), flow_type, amount, cash_delta, new_cash, str(payload.get("notes") or ""), now),
        ).lastrowid)
        portfolio["cash_balance"] = new_cash
        _insert_ledger(
            connection, portfolio, f"cash_{flow_type}", reference_id=flow_id, cash_delta=cash_delta,
            payload={"amount": amount, "notes": str(payload.get("notes") or "")}, created_at=now,
        )
        _insert_equity_snapshot(connection, portfolio_id, f"cash_{flow_type}")
    return {"cash_flow_id": flow_id, "snapshot": portfolio_snapshot(portfolio_id)}


def record_portfolio_valuation(portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    with connect() as connection:
        _portfolio_row(connection, portfolio_id)
        metrics, recorded = _insert_equity_snapshot(connection, portfolio_id, "manual_valuation")
    return {
        "recorded": recorded,
        "fingerprint": metrics["fingerprint"],
        "source_timestamp": metrics["source_timestamp"],
        "snapshot": portfolio_snapshot(portfolio_id),
    }


def reset_spot_portfolio(initial_cash: float, reason: str, portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    initial_cash = float(initial_cash)
    if initial_cash < 100 or initial_cash > 1_000_000_000:
        raise ValueError("Initial cash must be between 100 and 1,000,000,000")
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise ValueError("A reset reason is required for audit")
    now = now_iso()
    with connect() as connection:
        portfolio = _portfolio_row(connection, portfolio_id)
        next_cycle = int(portfolio.get("active_cycle") or 1) + 1
        connection.execute(
            """UPDATE spot_portfolios SET initial_cash = ?, cash_balance = ?, active_cycle = ?,
            updated_at = ? WHERE id = ?""",
            (initial_cash, initial_cash, next_cycle, now, portfolio_id),
        )
        connection.execute(
            "UPDATE spot_holdings SET quantity = 0, average_cost = 0, realized_pnl = 0, updated_at = ? WHERE portfolio_id = ?",
            (now, portfolio_id),
        )
        portfolio.update({"initial_cash": initial_cash, "cash_balance": initial_cash, "active_cycle": next_cycle, "updated_at": now})
        _insert_ledger(
            connection, portfolio, "portfolio_reset", cash_delta=0,
            payload={"reason": reason, "initial_cash": initial_cash, "previous_cycle": next_cycle - 1}, created_at=now,
        )
        _insert_equity_snapshot(connection, portfolio_id, "portfolio_reset")
    return {"cycle_number": next_cycle, "snapshot": portfolio_snapshot(portfolio_id)}


def project_contributions(initial_value: float, monthly_contribution: float, years: int, annual_return_pct: float) -> dict:
    months = years * 12
    monthly_rate = (1 + annual_return_pct / 100) ** (1 / 12) - 1
    value = float(initial_value)
    points = []
    contributed = float(initial_value)
    for month in range(1, months + 1):
        value = value * (1 + monthly_rate) + monthly_contribution
        contributed += monthly_contribution
        if month == 1 or month % 12 == 0 or month == months:
            points.append({"month": month, "value": round(value, 2), "contributed": round(contributed, 2)})
    return {
        "assumptions": {"initial_value": initial_value, "monthly_contribution": monthly_contribution, "years": years, "annual_return_pct": annual_return_pct},
        "final_value": round(value, 2), "total_contributed": round(contributed, 2),
        "mode": "user_assumption_scenario", "points": points,
        "warning": "Scenario math only; the annual return is a user assumption, not a forecast.",
    }
