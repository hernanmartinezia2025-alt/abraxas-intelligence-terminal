from __future__ import annotations

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
        (id, name, base_currency, initial_cash, cash_balance, created_at, updated_at)
        VALUES (?, 'ABRAXAS Spot Long Term', 'USDT', ?, ?, ?, ?)""",
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


def portfolio_snapshot(portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    with connect() as connection:
        seed_portfolio(connection)
        portfolio_row = connection.execute("SELECT * FROM spot_portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        if not portfolio_row:
            raise ValueError("Spot portfolio not found")
        portfolio = dict(portfolio_row)
        holdings = [dict(row) for row in connection.execute(
            "SELECT * FROM spot_holdings WHERE portfolio_id = ? AND quantity > 0 ORDER BY symbol", (portfolio_id,)
        ).fetchall()]
        market_value = 0.0
        cost_basis = 0.0
        unrealized_pnl = 0.0
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
        equity = float(portfolio["cash_balance"]) + market_value
        for holding in holdings:
            holding["weight_pct"] = holding["market_value"] / equity * 100 if equity else 0.0
        transactions = [dict(row) for row in connection.execute(
            "SELECT * FROM spot_transactions WHERE portfolio_id = ? ORDER BY id DESC LIMIT 100", (portfolio_id,)
        ).fetchall()]
    return {
        "portfolio": portfolio,
        "equity": equity,
        "market_value": market_value,
        "cost_basis": cost_basis,
        "unrealized_pnl": unrealized_pnl,
        "return_pct": unrealized_pnl / cost_basis * 100 if cost_basis else 0.0,
        "holdings": holdings,
        "transactions": transactions,
        "mode": "spot_simulation",
        "live_execution": "blocked",
    }


def execute_spot_transaction(payload: dict, portfolio_id: int = DEFAULT_PORTFOLIO_ID) -> dict:
    initialize_database()
    symbol = str(payload["symbol"]).upper().strip()
    side = str(payload["side"]).lower().strip()
    quantity = float(payload["quantity"])
    if side not in {"buy", "sell"} or quantity <= 0:
        raise ValueError("Invalid spot transaction")
    now = now_iso()
    with connect() as connection:
        seed_portfolio(connection)
        portfolio = dict(connection.execute("SELECT * FROM spot_portfolios WHERE id = ?", (portfolio_id,)).fetchone())
        mark = latest_mark(connection, symbol)
        price = mark["price"]
        notional = price * quantity
        fee = notional * FEE_RATE
        holding_row = connection.execute(
            "SELECT * FROM spot_holdings WHERE portfolio_id = ? AND symbol = ?", (portfolio_id, symbol)
        ).fetchone()
        holding = dict(holding_row) if holding_row else None
        realized = 0.0
        if side == "buy":
            if notional + fee > float(portfolio["cash_balance"]):
                raise ValueError("Insufficient spot simulation cash")
            old_qty = float(holding["quantity"]) if holding else 0.0
            old_avg = float(holding["average_cost"]) if holding else 0.0
            new_qty = old_qty + quantity
            new_avg = ((old_qty * old_avg) + notional + fee) / new_qty
            cash_delta = -(notional + fee)
        else:
            if not holding or float(holding["quantity"]) + 1e-12 < quantity:
                raise ValueError("Insufficient spot holding quantity")
            new_qty = float(holding["quantity"]) - quantity
            new_avg = float(holding["average_cost"]) if new_qty > 1e-12 else 0.0
            realized = quantity * (price - float(holding["average_cost"])) - fee
            cash_delta = notional - fee
        connection.execute(
            """INSERT INTO spot_holdings (portfolio_id, symbol, quantity, average_cost, realized_pnl, updated_at)
            VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(portfolio_id, symbol) DO UPDATE SET
            quantity=excluded.quantity, average_cost=excluded.average_cost,
            realized_pnl=spot_holdings.realized_pnl + excluded.realized_pnl, updated_at=excluded.updated_at""",
            (portfolio_id, symbol, new_qty, new_avg, realized, now),
        )
        connection.execute(
            "UPDATE spot_portfolios SET cash_balance = cash_balance + ?, updated_at = ? WHERE id = ?",
            (cash_delta, now, portfolio_id),
        )
        transaction_id = connection.execute(
            """INSERT INTO spot_transactions
            (portfolio_id, symbol, side, quantity, price, notional, fee, realized_pnl,
             price_timestamp, source, notes, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'market_snapshots', ?, ?)""",
            (portfolio_id, symbol, side, quantity, price, notional, fee, realized,
             mark["timestamp"], str(payload.get("notes") or ""), now),
        ).lastrowid
    return {"transaction_id": transaction_id, "snapshot": portfolio_snapshot(portfolio_id)}


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
