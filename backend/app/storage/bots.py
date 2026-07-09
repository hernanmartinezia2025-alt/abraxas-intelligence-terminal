from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_STRATEGY = {
    "engine": "rules",
    "entry": [
        {"field": "return_5", "operator": ">", "value": 0},
        {"field": "risk_score", "operator": "<", "value": 65},
    ],
    "exit": [
        {"field": "return_1", "operator": "<", "value": -0.6},
    ],
    "risk": {
        "max_position_pct": 10,
        "stop_loss_pct": 2,
        "take_profit_pct": 4,
    },
}


def normalize_bot(row: dict) -> dict:
    return {
        **row,
        "id": int(row["id"]),
    }


def normalize_version(row: dict) -> dict:
    try:
        strategy = json.loads(row.pop("strategy_json") or "{}")
    except json.JSONDecodeError:
        strategy = {}
    return {
        **row,
        "id": int(row["id"]),
        "bot_id": int(row["bot_id"]),
        "version": int(row["version"]),
        "strategy": strategy,
    }


def create_bot(payload: dict) -> dict:
    initialize_database()
    now = utc_now_iso()
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Bot name is required")

    strategy = payload.get("strategy") or DEFAULT_STRATEGY
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO bots (
                name, description, status, mode, base_symbol, timeframe,
                risk_profile, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                str(payload.get("description") or "Bot creado desde ABRAXAS Bot Forge."),
                "draft",
                "research",
                str(payload.get("base_symbol") or "BTCUSDT").upper(),
                str(payload.get("timeframe") or "15m"),
                str(payload.get("risk_profile") or "balanced"),
                now,
                now,
            ),
        )
        bot_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO bot_versions (bot_id, version, strategy_json, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                bot_id,
                1,
                json.dumps(strategy, ensure_ascii=True),
                str(payload.get("notes") or "Version inicial."),
                now,
            ),
        )
    return get_bot(bot_id)


def list_bots(limit: int = 100) -> dict:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, status, mode, base_symbol, timeframe,
                   risk_profile, created_at, updated_at
            FROM bots
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    bots = [normalize_bot(dict(row)) for row in rows]
    return {"bots": bots, "count": len(bots), "limit": limit}


def get_bot(bot_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        bot_row = connection.execute(
            """
            SELECT id, name, description, status, mode, base_symbol, timeframe,
                   risk_profile, created_at, updated_at
            FROM bots
            WHERE id = ?
            """,
            (bot_id,),
        ).fetchone()
        if not bot_row:
            raise ValueError("Bot not found")
        versions = connection.execute(
            """
            SELECT id, bot_id, version, strategy_json, notes, created_at
            FROM bot_versions
            WHERE bot_id = ?
            ORDER BY version DESC
            """,
            (bot_id,),
        ).fetchall()
    return {
        "bot": normalize_bot(dict(bot_row)),
        "versions": [normalize_version(dict(row)) for row in versions],
    }


def create_bot_version(bot_id: int, payload: dict) -> dict:
    initialize_database()
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        raise ValueError("strategy must be a JSON object")
    now = utc_now_iso()
    with connect() as connection:
        existing = connection.execute("SELECT id FROM bots WHERE id = ?", (bot_id,)).fetchone()
        if not existing:
            raise ValueError("Bot not found")
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS latest FROM bot_versions WHERE bot_id = ?",
            (bot_id,),
        ).fetchone()
        next_version = int(row["latest"]) + 1
        connection.execute(
            """
            INSERT INTO bot_versions (bot_id, version, strategy_json, notes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                bot_id,
                next_version,
                json.dumps(strategy, ensure_ascii=True),
                str(payload.get("notes") or f"Version {next_version}."),
                now,
            ),
        )
        connection.execute("UPDATE bots SET updated_at = ? WHERE id = ?", (now, bot_id))
    return get_bot(bot_id)
