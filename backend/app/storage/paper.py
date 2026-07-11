from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app.storage.risk import validate_order_intent
from backend.app.storage.sqlite import connect, initialize_database

ACCOUNT_ID = 1
DEFAULT_BALANCE = 10_000.0
FEE_RATE = 0.001


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_account(connection) -> None:
    now = utc_now_iso()
    connection.execute(
        """INSERT OR IGNORE INTO simulated_accounts
        (id, initial_balance, cash_balance, realized_pnl, peak_equity, created_at, updated_at)
        VALUES (?, ?, ?, 0, ?, ?, ?)""",
        (ACCOUNT_ID, DEFAULT_BALANCE, DEFAULT_BALANCE, DEFAULT_BALANCE, now, now),
    )


def latest_price(connection, symbol: str) -> float:
    row = connection.execute(
        "SELECT price FROM market_snapshots WHERE symbol = ? ORDER BY timestamp DESC, id DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    if not row:
        raise ValueError(f"No persisted market snapshot is available for {symbol}")
    return float(row["price"])


def bot_performance(connection, session_started_at: str) -> list[dict]:
    bots = [dict(row) for row in connection.execute(
        "SELECT id, name, base_symbol, timeframe, risk_profile, status FROM bots ORDER BY id DESC"
    ).fetchall()]
    results = []
    for bot in bots:
        orders = [dict(row) for row in connection.execute(
            "SELECT * FROM simulated_orders WHERE bot_id = ? AND created_at >= ? ORDER BY id",
            (bot["id"], session_started_at),
        ).fetchall()]
        fills = [dict(row) for row in connection.execute(
            """SELECT f.* FROM simulated_fills f JOIN simulated_orders o ON o.id = f.order_id
            WHERE o.bot_id = ? AND f.filled_at >= ? ORDER BY f.id""",
            (bot["id"], session_started_at),
        ).fetchall()]
        quantities: dict[str, float] = {}
        cash_flow = 0.0
        deployed = 0.0
        fees = 0.0
        for fill in fills:
            symbol = fill["symbol"]
            quantity = float(fill["quantity"])
            notional = quantity * float(fill["price"])
            fee = float(fill["fee"])
            fees += fee
            if fill["side"] == "buy":
                quantities[symbol] = quantities.get(symbol, 0.0) + quantity
                cash_flow -= notional + fee
                deployed += notional + fee
            else:
                quantities[symbol] = quantities.get(symbol, 0.0) - quantity
                cash_flow += notional - fee
        open_value = 0.0
        open_positions = []
        for symbol, quantity in quantities.items():
            if quantity <= 1e-12:
                continue
            price = latest_price(connection, symbol)
            value = quantity * price
            open_value += value
            open_positions.append({"symbol": symbol, "quantity": quantity, "market_price": price, "market_value": value})
        pnl = cash_flow + open_value
        roi_pct = (pnl / deployed) * 100 if deployed else 0.0
        results.append({
            **bot,
            "paper_status": "activity" if orders else "no_activity",
            "roi_pct": roi_pct,
            "pnl": pnl,
            "deployed_capital": deployed,
            "open_value": open_value,
            "fees": fees,
            "filled_orders": sum(order["status"] == "filled" for order in orders),
            "rejected_orders": sum(order["status"] == "rejected" for order in orders),
            "started_at": orders[0]["created_at"] if orders else None,
            "last_activity_at": orders[-1]["created_at"] if orders else None,
            "open_positions": open_positions,
        })
    return results


def account_snapshot() -> dict:
    initialize_database()
    with connect() as connection:
        seed_account(connection)
        account = dict(connection.execute("SELECT * FROM simulated_accounts WHERE id = ?", (ACCOUNT_ID,)).fetchone())
        daily_realized = float(connection.execute(
            "SELECT COALESCE(SUM(realized_pnl_delta), 0) AS value FROM simulated_ledger WHERE account_id = ? AND date(created_at) = date('now')",
            (ACCOUNT_ID,),
        ).fetchone()["value"])
        positions = [dict(row) for row in connection.execute(
            "SELECT * FROM simulated_positions WHERE account_id = ? AND quantity > 0 ORDER BY symbol",
            (ACCOUNT_ID,),
        ).fetchall()]
        market_value = 0.0
        unrealized_pnl = 0.0
        for position in positions:
            price = latest_price(connection, position["symbol"])
            position["market_price"] = price
            position["market_value"] = position["quantity"] * price
            position["unrealized_pnl"] = position["quantity"] * (price - position["average_price"])
            market_value += position["market_value"]
            unrealized_pnl += position["unrealized_pnl"]
        equity = float(account["cash_balance"]) + market_value
        peak = max(float(account["peak_equity"]), equity)
        if peak != float(account["peak_equity"]):
            connection.execute("UPDATE simulated_accounts SET peak_equity = ?, updated_at = ? WHERE id = ?", (peak, utc_now_iso(), ACCOUNT_ID))
        drawdown = ((equity / peak) - 1) * 100 if peak else 0.0
        orders = [dict(row) for row in connection.execute("SELECT * FROM simulated_orders ORDER BY id DESC LIMIT 30").fetchall()]
        fills = [dict(row) for row in connection.execute("SELECT * FROM simulated_fills ORDER BY id DESC LIMIT 30").fetchall()]
        performance = bot_performance(connection, account["created_at"])
    return {"account": account, "equity": equity, "market_value": market_value, "unrealized_pnl": unrealized_pnl, "daily_realized_pnl": daily_realized, "drawdown_pct": abs(drawdown), "positions": positions, "orders": orders, "fills": fills, "bot_performance": performance, "mode": "paper", "live_execution": "blocked"}


def place_market_order(payload: dict) -> dict:
    initialize_database()
    symbol = str(payload["symbol"]).strip().upper()
    side = str(payload["side"]).strip().lower()
    quantity = float(payload["quantity"])
    bot_id = payload.get("bot_id")
    now = utc_now_iso()
    snapshot = account_snapshot()
    with connect() as connection:
        seed_account(connection)
        price = latest_price(connection, symbol)
    notional = price * quantity
    decision = validate_order_intent({
        "mode": "paper", "symbol": symbol, "side": "long", "requested_notional": notional,
        "account_equity": snapshot["equity"], "daily_pnl": snapshot["daily_realized_pnl"],
        "current_drawdown_pct": snapshot["drawdown_pct"], "last_loss_at": None,
        "reduces_exposure": side == "sell",
    })
    with connect() as connection:
        seed_account(connection)
        account = dict(connection.execute("SELECT * FROM simulated_accounts WHERE id = ?", (ACCOUNT_ID,)).fetchone())
        position_row = connection.execute("SELECT * FROM simulated_positions WHERE account_id = ? AND symbol = ?", (ACCOUNT_ID, symbol)).fetchone()
        position = dict(position_row) if position_row else None
        rejection = None
        fee = notional * FEE_RATE
        if not decision["approved"]:
            rejection = "; ".join(decision["reasons"])
        elif side == "buy" and notional + fee > float(account["cash_balance"]):
            rejection = "Insufficient simulated cash balance"
        elif side == "sell" and (not position or float(position["quantity"]) < quantity):
            rejection = "Insufficient simulated position quantity"
        status = "rejected" if rejection else "filled"
        cursor = connection.execute(
            """INSERT INTO simulated_orders
            (account_id, bot_id, symbol, side, quantity, status, reference_price, fill_price, fee, risk_validation_id, rejection_reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ACCOUNT_ID, bot_id, symbol, side, quantity, status, price, price if not rejection else None, fee if not rejection else None, decision["validation_id"], rejection, now),
        )
        order_id = cursor.lastrowid
        if rejection:
            return {"order_id": order_id, "status": status, "reason": rejection, "risk": decision, "execution_performed": False}

        realized_delta = 0.0
        if side == "buy":
            old_qty = float(position["quantity"]) if position else 0.0
            old_avg = float(position["average_price"]) if position else 0.0
            new_qty = old_qty + quantity
            new_avg = ((old_qty * old_avg) + notional) / new_qty
            connection.execute(
                """INSERT INTO simulated_positions (account_id, symbol, quantity, average_price, realized_pnl, updated_at)
                VALUES (?, ?, ?, ?, 0, ?) ON CONFLICT(account_id, symbol) DO UPDATE SET
                quantity = excluded.quantity, average_price = excluded.average_price, updated_at = excluded.updated_at""",
                (ACCOUNT_ID, symbol, new_qty, new_avg, now),
            )
            cash_delta = -(notional + fee)
        else:
            realized_delta = quantity * (price - float(position["average_price"])) - fee
            new_qty = float(position["quantity"]) - quantity
            connection.execute("UPDATE simulated_positions SET quantity = ?, realized_pnl = realized_pnl + ?, updated_at = ? WHERE id = ?", (new_qty, realized_delta, now, position["id"]))
            cash_delta = notional - fee
        new_cash = float(account["cash_balance"]) + cash_delta
        connection.execute("UPDATE simulated_accounts SET cash_balance = ?, realized_pnl = realized_pnl + ?, updated_at = ? WHERE id = ?", (new_cash, realized_delta, now, ACCOUNT_ID))
        fill_id = connection.execute("INSERT INTO simulated_fills (order_id, account_id, symbol, side, quantity, price, fee, filled_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (order_id, ACCOUNT_ID, symbol, side, quantity, price, fee, now)).lastrowid
        connection.execute("INSERT INTO simulated_ledger (account_id, event_type, reference_id, symbol, cash_delta, realized_pnl_delta, cash_balance, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (ACCOUNT_ID, "market_fill", fill_id, symbol, cash_delta, realized_delta, new_cash, json.dumps({"order_id": order_id, "side": side, "quantity": quantity, "price": price, "fee": fee}), now))
    return {"order_id": order_id, "fill_id": fill_id, "status": status, "risk": decision, "execution_performed": True, "account": account_snapshot()}


def reset_account(initial_balance: float, reason: str) -> dict:
    initialize_database()
    now = utc_now_iso()
    with connect() as connection:
        seed_account(connection)
        connection.execute("DELETE FROM simulated_positions WHERE account_id = ?", (ACCOUNT_ID,))
        connection.execute("UPDATE simulated_accounts SET initial_balance = ?, cash_balance = ?, realized_pnl = 0, peak_equity = ?, created_at = ?, updated_at = ? WHERE id = ?", (initial_balance, initial_balance, initial_balance, now, now, ACCOUNT_ID))
        connection.execute("INSERT INTO simulated_ledger (account_id, event_type, reference_id, symbol, cash_delta, realized_pnl_delta, cash_balance, payload_json, created_at) VALUES (?, 'account_reset', NULL, NULL, 0, 0, ?, ?, ?)", (ACCOUNT_ID, initial_balance, json.dumps({"reason": reason, "initial_balance": initial_balance}), now))
    return account_snapshot()
