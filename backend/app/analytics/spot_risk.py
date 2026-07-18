from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def build_spot_risk_context(snapshot: dict, evaluated_at: datetime | None = None) -> dict:
    now = (evaluated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    equity = float(snapshot["equity"])
    history = sorted(snapshot.get("equity_history") or [], key=lambda row: row["recorded_at"])
    cycle = int(snapshot["portfolio"]["active_cycle"])
    cycle_history = [row for row in history if int(row.get("cycle_number") or cycle) == cycle]
    peak_equity = max([equity, *[float(row["equity"]) for row in cycle_history]])
    drawdown_pct = max(0.0, (peak_equity - equity) / peak_equity * 100) if peak_equity else 0.0

    window_start = now - timedelta(hours=24)
    window_rows = [row for row in cycle_history if _utc(row["recorded_at"]) >= window_start]
    baseline = window_rows[0] if window_rows else None
    if baseline:
        baseline_time = _utc(baseline["recorded_at"])
        cash_flows = sum(
            float(row.get("cash_delta") or 0)
            for row in snapshot.get("cash_flows") or []
            if _utc(row["created_at"]) >= baseline_time
        )
        daily_pnl = equity - float(baseline["equity"]) - cash_flows
        coverage = "observed_window"
        observed_since = baseline["recorded_at"]
    else:
        daily_pnl = 0.0
        coverage = "current_baseline_only"
        observed_since = now.isoformat()

    losing_transactions = [
        row for row in snapshot.get("transactions") or []
        if float(row.get("realized_pnl") or 0) < 0
    ]
    last_loss_at = max((row["executed_at"] for row in losing_transactions), default=None)
    return {
        "account_equity": equity,
        "daily_pnl": daily_pnl,
        "current_drawdown_pct": drawdown_pct,
        "peak_equity": peak_equity,
        "last_loss_at": last_loss_at,
        "coverage": coverage,
        "observed_since": observed_since,
        "evaluated_at": now.isoformat(),
    }
