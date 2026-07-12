from __future__ import annotations

from datetime import datetime, timezone

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
        proposal_id = connection.execute(
            """
            INSERT INTO paper_order_proposals (
                signal_evaluation_id, bot_id, bot_version_id, symbol, action,
                quantity, reference_price, proposed_notional, status, reason,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                payload["signal_evaluation_id"], payload["bot_id"], payload["bot_version_id"],
                payload["symbol"], payload["action"], payload["quantity"], payload["reference_price"],
                payload["proposed_notional"], payload["reason"], now, now,
            ),
        ).lastrowid
        row = connection.execute("SELECT * FROM paper_order_proposals WHERE id = ?", (proposal_id,)).fetchone()
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
