from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.app.storage.sqlite import connect, initialize_database


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_paper_proposal(payload: dict) -> dict:
    initialize_database()
    now = utc_now_iso()
    with connect() as connection:
        existing = connection.execute(
            "SELECT * FROM paper_order_proposals WHERE signal_evaluation_id = ?",
            (payload["signal_evaluation_id"],),
        ).fetchone()
        if existing:
            return dict(existing)
        connection.execute(
            """
            INSERT OR IGNORE INTO paper_order_proposals (
                signal_evaluation_id, bot_id, bot_version_id, symbol, action,
                quantity, reference_price, proposed_notional, status, reason, strategy_hash,
                price_timestamp, expires_at, allocation_id, allocation_revision, trigger_reason,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["signal_evaluation_id"], payload["bot_id"], payload["bot_version_id"],
                payload["symbol"], payload["action"], payload["quantity"], payload["reference_price"],
                payload["proposed_notional"], payload["reason"], payload.get("strategy_hash"),
                payload.get("price_timestamp"), payload.get("expires_at"), payload.get("allocation_id"),
                payload.get("allocation_revision"), payload.get("trigger_reason"), now, now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM paper_order_proposals WHERE signal_evaluation_id = ?", (payload["signal_evaluation_id"],)
        ).fetchone()
    return dict(row)


def list_paper_proposals(bot_id: int, limit: int = 50) -> dict:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM paper_order_proposals WHERE bot_id = ? ORDER BY id DESC LIMIT ?",
            (bot_id, limit),
        ).fetchall()
    proposals = [dict(row) for row in rows]
    return {"proposals": proposals, "count": len(proposals), "bot_id": bot_id, "limit": limit}


def get_paper_proposal(proposal_id: int) -> dict:
    initialize_database()
    with connect() as connection:
        row = connection.execute("SELECT * FROM paper_order_proposals WHERE id = ?", (proposal_id,)).fetchone()
    if not row:
        raise ValueError("Paper proposal not found")
    return dict(row)


def dismiss_paper_proposal(proposal_id: int, bot_id: int) -> dict:
    proposal = get_paper_proposal(proposal_id)
    if int(proposal["bot_id"]) != bot_id:
        raise ValueError("Paper proposal does not belong to this bot")
    if proposal["status"] != "pending" or proposal.get("claim_token"):
        raise ValueError("Only pending paper proposals can be dismissed")
    now = utc_now_iso()
    with connect() as connection:
        cursor = connection.execute(
            "UPDATE paper_order_proposals SET status = 'dismissed', updated_at = ? WHERE id = ? AND status = 'pending' AND claim_token IS NULL",
            (now, proposal_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Paper proposal was already processed")
    return get_paper_proposal(proposal_id)


def mark_paper_proposal_submitted(proposal_id: int, bot_id: int, result: dict, claim_token: str | None = None) -> dict:
    proposal = get_paper_proposal(proposal_id)
    if int(proposal["bot_id"]) != bot_id:
        raise ValueError("Paper proposal does not belong to this bot")
    if proposal["status"] != "pending":
        raise ValueError("Only pending paper proposals can be submitted")
    now = utc_now_iso()
    reference = f"simulated_order:{result['order_id']}" if result.get("order_id") else result.get("reason")
    with connect() as connection:
        where_claim = " AND claim_token = ?" if claim_token else ""
        parameters = [result.get("intent_id"), (result.get("risk") or {}).get("validation_id"), reference, now, now, proposal_id]
        if claim_token:
            parameters.append(claim_token)
        cursor = connection.execute(
            f"""UPDATE paper_order_proposals SET status = 'submitted', execution_intent_id = ?,
               risk_validation_id = ?, result_reference = ?, submitted_at = ?, updated_at = ?,
               claim_token = NULL, claimed_at = NULL, last_error = NULL
               WHERE id = ? AND status = 'pending'{where_claim}""",
            parameters,
        )
        if cursor.rowcount != 1:
            raise ValueError("Paper proposal was already processed")
    return get_paper_proposal(proposal_id)


def claim_paper_proposal(proposal_id: int, bot_id: int) -> dict:
    proposal = get_paper_proposal(proposal_id)
    if int(proposal["bot_id"]) != bot_id:
        raise ValueError("Paper proposal does not belong to this bot")
    if proposal["status"] != "pending":
        raise ValueError("Paper proposal was already processed")
    now = utc_now_iso()
    token = str(uuid4())
    stale_before = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """UPDATE paper_order_proposals SET claim_token = ?, claimed_at = ?,
               attempt_count = attempt_count + 1, last_error = NULL, updated_at = ?
               WHERE id = ? AND bot_id = ? AND status = 'pending'
               AND (claim_token IS NULL OR claimed_at < ?)""",
            (token, now, now, proposal_id, bot_id, stale_before),
        )
        if cursor.rowcount != 1:
            raise ValueError("Paper proposal was already processed")
    claimed = get_paper_proposal(proposal_id)
    claimed["_claim_token"] = token
    return claimed


def release_paper_proposal_claim(proposal_id: int, claim_token: str, error: str | None = None) -> None:
    with connect() as connection:
        connection.execute(
            """UPDATE paper_order_proposals SET claim_token = NULL, claimed_at = NULL,
               last_error = ?, updated_at = ? WHERE id = ? AND claim_token = ? AND status = 'pending'""",
            (error, utc_now_iso(), proposal_id, claim_token),
        )
