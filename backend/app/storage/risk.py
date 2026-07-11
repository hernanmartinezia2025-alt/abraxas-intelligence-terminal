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
    for event in events:
        event["payload"] = json.loads(event.pop("payload_json"))
    return {
        "limits": limits,
        "kill_switch": {
            "active": bool(state["kill_switch_active"]),
            "reason": state["reason"],
            "updated_at": state["updated_at"],
        },
        "execution": {"paper": "blocked", "live": "blocked"},
        "audit_log": events,
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
