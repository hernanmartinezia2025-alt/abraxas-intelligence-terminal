from __future__ import annotations

import json

from backend.app.execution.contracts import OrderIntent, utc_now_iso
from backend.app.storage.sqlite import connect, initialize_database


def save_execution_intent(intent: OrderIntent) -> dict:
    initialize_database()
    payload = intent.to_dict()
    with connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO execution_intents (
                id, environment, adapter, symbol, action, order_type, quantity,
                limit_price, bot_id, bot_version_id, strategy_hash, signal_evaluation_id,
                proposal_id, status, result_reference, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'created', NULL, ?, ?, ?)""",
            (
                intent.id, intent.environment, intent.adapter, intent.symbol, intent.action,
                intent.order_type, intent.quantity, intent.limit_price, intent.bot_id,
                intent.bot_version_id, intent.strategy_hash, intent.signal_evaluation_id, intent.proposal_id,
                json.dumps(payload, sort_keys=True), intent.created_at, intent.created_at,
            ),
        )
    return {**payload, "status": "created", "result_reference": None}


def get_execution_intent(intent_id: str) -> dict | None:
    initialize_database()
    with connect() as connection:
        row = connection.execute("SELECT * FROM execution_intents WHERE id = ?", (intent_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["payload"] = json.loads(result.pop("payload_json") or "{}")
    return result


def update_execution_intent(
    intent_id: str,
    status: str,
    result_reference: str | None = None,
    risk_validation_id: int | None = None,
    connection=None,
) -> None:
    def execute(active_connection) -> None:
        updated = active_connection.execute(
            """UPDATE execution_intents
            SET status = ?, result_reference = ?, risk_validation_id = ?, updated_at = ?
            WHERE id = ?""",
            (status, result_reference, risk_validation_id, utc_now_iso(), intent_id),
        )
        if updated.rowcount != 1:
            raise ValueError(f"Execution intent not found: {intent_id}")

    if connection is not None:
        execute(connection)
        return
    with connect() as owned_connection:
        execute(owned_connection)
