from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


DEFAULT_LIMITS = {
    "max_position_pct": 10.0,
    "max_daily_loss_pct": 3.0,
    "max_drawdown_pct": 12.0,
    "cooldown_minutes": 30,
    "symbol_whitelist": ["BTCUSDT", "ETHUSDT"],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed(connection) -> None:
    now = utc_now_iso()
    connection.execute(
        """
        INSERT OR IGNORE INTO risk_limits (
            id, max_position_pct, max_daily_loss_pct, max_drawdown_pct,
            cooldown_minutes, symbol_whitelist, updated_at
        ) VALUES (1, ?, ?, ?, ?, ?, ?)
        """,
        (
            DEFAULT_LIMITS["max_position_pct"],
            DEFAULT_LIMITS["max_daily_loss_pct"],
            DEFAULT_LIMITS["max_drawdown_pct"],
            DEFAULT_LIMITS["cooldown_minutes"],
            json.dumps(DEFAULT_LIMITS["symbol_whitelist"]),
            now,
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO risk_state (id, kill_switch_active, reason, updated_at)
        VALUES (1, 1, 'Safe default: execution remains locked', ?)
        """,
        (now,),
    )


def _limits(row) -> dict:
    return {
        "max_position_pct": float(row["max_position_pct"]),
        "max_daily_loss_pct": float(row["max_daily_loss_pct"]),
        "max_drawdown_pct": float(row["max_drawdown_pct"]),
        "cooldown_minutes": int(row["cooldown_minutes"]),
        "symbol_whitelist": json.loads(row["symbol_whitelist"]),
        "updated_at": row["updated_at"],
    }


def get_risk_profile(audit_limit: int = 20) -> dict:
    initialize_database()
    with connect() as connection:
        _seed(connection)
        limits = _limits(connection.execute("SELECT * FROM risk_limits WHERE id = 1").fetchone())
        state = dict(connection.execute("SELECT * FROM risk_state WHERE id = 1").fetchone())
        events = [dict(row) for row in connection.execute(
            "SELECT id, event_type, payload_json, created_at FROM risk_audit_log ORDER BY id DESC LIMIT ?",
            (audit_limit,),
        ).fetchall()]
        validations = [dict(row) for row in connection.execute(
            """SELECT validation.id, validation.mode, validation.symbol, validation.approved,
            validation.request_json, validation.decision_json, validation.created_at,
            intent.id AS execution_intent_id, intent.status AS execution_status,
            intent.result_reference
            FROM risk_validation_log AS validation
            LEFT JOIN execution_intents AS intent ON intent.risk_validation_id = validation.id
            ORDER BY validation.id DESC LIMIT ?""",
            (audit_limit,),
        ).fetchall()]
    for event in events:
        event["payload"] = json.loads(event.pop("payload_json"))
    for validation in validations:
        validation["approved"] = bool(validation["approved"])
        validation["request"] = json.loads(validation.pop("request_json"))
        validation["decision"] = json.loads(validation.pop("decision_json"))
    return {
        "limits": limits,
        "kill_switch": {
            "active": bool(state["kill_switch_active"]),
            "reason": state["reason"],
            "updated_at": state["updated_at"],
        },
        "execution": {"paper": "risk_gated", "spot_simulation": "risk_gated", "live": "blocked"},
        "audit_log": events,
        "validation_log": validations,
    }


def update_risk_limits(payload: dict) -> dict:
    initialize_database()
    now = utc_now_iso()
    symbols = sorted({str(symbol).strip().upper() for symbol in payload["symbol_whitelist"] if str(symbol).strip()})
    if not symbols:
        raise ValueError("Symbol whitelist must contain at least one symbol")
    normalized = {**payload, "symbol_whitelist": symbols}
    with connect() as connection:
        _seed(connection)
        connection.execute(
            """
            UPDATE risk_limits SET max_position_pct = ?, max_daily_loss_pct = ?,
                max_drawdown_pct = ?, cooldown_minutes = ?, symbol_whitelist = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                normalized["max_position_pct"], normalized["max_daily_loss_pct"],
                normalized["max_drawdown_pct"], normalized["cooldown_minutes"],
                json.dumps(symbols), now,
            ),
        )
        connection.execute(
            "INSERT INTO risk_audit_log (event_type, payload_json, created_at) VALUES (?, ?, ?)",
            ("limits_updated", json.dumps(normalized, sort_keys=True), now),
        )
    return get_risk_profile()


def set_kill_switch(active: bool, reason: str) -> dict:
    initialize_database()
    now = utc_now_iso()
    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError("A reason is required for every kill switch change")
    payload = {"active": active, "reason": clean_reason}
    with connect() as connection:
        _seed(connection)
        connection.execute(
            "UPDATE risk_state SET kill_switch_active = ?, reason = ?, updated_at = ? WHERE id = 1",
            (int(active), clean_reason, now),
        )
        connection.execute(
            "INSERT INTO risk_audit_log (event_type, payload_json, created_at) VALUES (?, ?, ?)",
            ("kill_switch_changed", json.dumps(payload, sort_keys=True), now),
        )
    return get_risk_profile()


def get_risk_validation(validation_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM risk_validation_log WHERE id = ?",
            (validation_id,),
        ).fetchone()
    if not row:
        raise ValueError("Risk validation not found")
    validation = dict(row)
    validation["approved"] = bool(validation["approved"])
    validation["request"] = json.loads(validation.pop("request_json"))
    validation["decision"] = json.loads(validation.pop("decision_json"))
    return validation


def validate_order_intent(payload: dict, *, persist: bool = True) -> dict:
    initialize_database()
    now = datetime.now(timezone.utc)
    symbol = str(payload["symbol"]).strip().upper()
    mode = str(payload["mode"]).strip().lower()
    side = str(payload["side"]).strip().lower()
    account_equity = float(payload["account_equity"])
    requested_notional = float(payload["requested_notional"])
    current_exposure_notional = max(0.0, float(payload.get("current_exposure_notional") or 0))
    daily_pnl = float(payload["daily_pnl"])
    current_drawdown_pct = float(payload["current_drawdown_pct"])

    with connect() as connection:
        _seed(connection)
        limits = _limits(connection.execute("SELECT * FROM risk_limits WHERE id = 1").fetchone())
        state = dict(connection.execute("SELECT * FROM risk_state WHERE id = 1").fetchone())

        reduces_exposure = bool(payload.get("reduces_exposure"))
        projected_exposure_notional = max(0.0, current_exposure_notional - requested_notional) if reduces_exposure else current_exposure_notional + requested_notional
        current_position_pct = (current_exposure_notional / account_equity) * 100
        position_pct = (projected_exposure_notional / account_equity) * 100
        daily_loss_pct = max(0.0, (-daily_pnl / account_equity) * 100)
        reasons = []
        checks = []

        def check(code: str, passed: bool, detail: str) -> None:
            checks.append({"code": code, "passed": passed, "detail": detail})
            if not passed:
                reasons.append(detail)

        kill_allowed = reduces_exposure or not bool(state["kill_switch_active"])
        check("kill_switch", kill_allowed, "Close-only reduction allowed while kill switch is active" if reduces_exposure and bool(state["kill_switch_active"]) else ("Kill switch inactive" if not bool(state["kill_switch_active"]) else "Kill switch is active"))
        mode_allowed = mode in {"validation", "paper", "spot"}
        check("mode", mode_allowed, f"{mode.title()} mode allowed" if mode_allowed else "Live mode is blocked")
        check("side", side == "long", "Long intent supported" if side == "long" else "Only long intents are supported in this phase")
        symbol_allowed = reduces_exposure or symbol in limits["symbol_whitelist"]
        check(
            "symbol_whitelist",
            symbol_allowed,
            "Close-only reduction bypasses symbol whitelist"
            if reduces_exposure and symbol not in limits["symbol_whitelist"]
            else (f"{symbol} is authorized" if symbol_allowed else f"{symbol} is outside the symbol whitelist"),
        )
        position_allowed = reduces_exposure or position_pct <= limits["max_position_pct"]
        position_detail = f"Exposure reduces from {current_position_pct:.2f}% to {position_pct:.2f}%" if reduces_exposure else (f"Projected exposure {position_pct:.2f}% within limit" if position_allowed else f"Projected exposure {position_pct:.2f}% exceeds {limits['max_position_pct']:.2f}%")
        check("max_position", position_allowed, position_detail)
        daily_allowed = reduces_exposure or daily_loss_pct < limits["max_daily_loss_pct"]
        drawdown_allowed = reduces_exposure or current_drawdown_pct < limits["max_drawdown_pct"]
        check("max_daily_loss", daily_allowed, "Close-only reduction bypasses entry loss limit" if reduces_exposure else (f"Daily loss {daily_loss_pct:.2f}% within limit" if daily_allowed else f"Daily loss {daily_loss_pct:.2f}% reached limit {limits['max_daily_loss_pct']:.2f}%"))
        check("max_drawdown", drawdown_allowed, "Close-only reduction bypasses entry drawdown limit" if reduces_exposure else (f"Drawdown {current_drawdown_pct:.2f}% within limit" if drawdown_allowed else f"Drawdown {current_drawdown_pct:.2f}% reached limit {limits['max_drawdown_pct']:.2f}%"))

        last_loss_at = payload.get("last_loss_at")
        cooldown_remaining = 0
        if last_loss_at:
            loss_time = datetime.fromisoformat(str(last_loss_at).replace("Z", "+00:00"))
            if loss_time.tzinfo is None:
                loss_time = loss_time.replace(tzinfo=timezone.utc)
            elapsed_minutes = max(0, int((now - loss_time.astimezone(timezone.utc)).total_seconds() // 60))
            cooldown_remaining = max(0, limits["cooldown_minutes"] - elapsed_minutes)
        cooldown_allowed = reduces_exposure or cooldown_remaining == 0
        check("cooldown", cooldown_allowed, "Close-only reduction bypasses entry cooldown" if reduces_exposure else ("Cooldown clear" if cooldown_allowed else f"Cooldown has {cooldown_remaining} minutes remaining"))

        approved = not reasons
        decision = {
            "approved": approved,
            "decision": "approved" if approved else "rejected",
            "reasons": reasons,
            "checks": checks,
            "metrics": {
                "position_pct": round(position_pct, 4),
                "current_position_pct": round(current_position_pct, 4),
                "projected_exposure_notional": round(projected_exposure_notional, 8),
                "daily_loss_pct": round(daily_loss_pct, 4),
                "current_drawdown_pct": round(current_drawdown_pct, 4),
                "cooldown_remaining_minutes": cooldown_remaining,
                "close_only": reduces_exposure,
            },
            "limits_version": limits["updated_at"],
            "evaluated_at": now.isoformat(),
            "execution_performed": False,
        }
        normalized_request = {**payload, "symbol": symbol, "mode": mode, "side": side}
        if persist:
            cursor = connection.execute(
                """
                INSERT INTO risk_validation_log (
                    mode, symbol, approved, request_json, decision_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mode, symbol, int(approved), json.dumps(normalized_request, sort_keys=True), json.dumps(decision, sort_keys=True), now.isoformat()),
            )
            decision["validation_id"] = cursor.lastrowid
        else:
            decision["validation_id"] = None
            decision["persistence"] = "preview_only"
    return decision
