from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_signal_evaluation(payload: dict) -> dict:
    initialize_database()
    evaluated_at = utc_now_iso()
    evaluation_key = hashlib.sha256(
        f"{payload['bot_version_id']}:{payload['strategy_hash']}:{payload['feature_timestamp']}".encode("utf-8")
    ).hexdigest()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO strategy_signal_evaluations (
                bot_id, bot_version_id, strategy_hash, symbol, timeframe,
                feature_timestamp, evaluation_key, signal, entry_passed, exit_passed, conflict,
                features_json, trace_json, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(evaluation_key) DO NOTHING
            """,
            (
                payload["bot_id"], payload["bot_version_id"], payload["strategy_hash"],
                payload["symbol"], payload["timeframe"], payload["feature_timestamp"], evaluation_key,
                payload["signal"], int(payload["entry_passed"]), int(payload["exit_passed"]), int(payload.get("conflict", False)),
                json.dumps(payload["features"], ensure_ascii=True),
                json.dumps(payload["trace"], ensure_ascii=True), evaluated_at,
            ),
        )
        evaluation_id = int(connection.execute(
            "SELECT id FROM strategy_signal_evaluations WHERE evaluation_key = ?", (evaluation_key,)
        ).fetchone()["id"])
    return get_signal_evaluation(evaluation_id)


def _normalize(row: dict) -> dict:
    features = json.loads(row.pop("features_json"))
    trace = json.loads(row.pop("trace_json"))
    return {
        **row,
        "id": int(row["id"]),
        "bot_id": int(row["bot_id"]),
        "bot_version_id": int(row["bot_version_id"]),
        "feature_timestamp": int(row["feature_timestamp"]),
        "entry_passed": bool(row["entry_passed"]),
        "exit_passed": bool(row["exit_passed"]),
        "conflict": bool(row.get("conflict")),
        "features": features,
        "trace": trace,
        "execution_intent_created": False,
    }


def get_signal_evaluation(evaluation_id: int) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM strategy_signal_evaluations WHERE id = ?", (evaluation_id,)).fetchone()
    if not row:
        raise ValueError("Signal evaluation not found")
    return _normalize(dict(row))


def list_signal_evaluations(bot_id: int, limit: int = 50) -> dict:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM strategy_signal_evaluations WHERE bot_id = ? ORDER BY id DESC LIMIT ?",
            (bot_id, limit),
        ).fetchall()
    evaluations = [_normalize(dict(row)) for row in rows]
    return {"evaluations": evaluations, "count": len(evaluations), "bot_id": bot_id, "limit": limit}
