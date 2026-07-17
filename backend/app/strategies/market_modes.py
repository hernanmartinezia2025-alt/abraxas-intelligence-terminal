from __future__ import annotations


def build_market_mode_policy(timeframe: str, risk_profile: dict | None = None) -> dict:
    """Describe hard boundaries between wealth-building spot and futures trading."""
    profile = risk_profile or {}
    limits = profile.get("limits") or {}
    kill_switch = profile.get("kill_switch") or {}
    spot_timeframes = {"1d", "1w"}
    return {
        "contract": "market_mode_separation_v1",
        "active_mode": "spot_portfolio_simulation",
        "mode_conversion": "forbidden",
        "spot": {
            "status": "simulation_only",
            "objective": "long_term_capital_accumulation",
            "analysis_timeframes": ["1d", "1w"],
            "current_timeframe": timeframe,
            "timeframe_allowed": timeframe in spot_timeframes,
            "position_direction": "long_only",
            "leverage": 1,
            "dca": "manual_and_allocation_limited",
            "stop_loss": "not_automatic_for_long_term_spot",
            "risk_boundary": (
                "No stop loss does not mean no loss: unrealized drawdown, asset failure, "
                "custody risk and opportunity cost remain real. DCA requires a validated asset thesis."
            ),
        },
        "futures": {
            "status": "locked",
            "objective": "short_term_cash_flow_planned",
            "analysis_timeframes": ["1h", "4h"],
            "execution_supported": False,
            "leverage": {"planned_default_min": 3, "planned_default_max": 5, "hard_max": 10},
            "stop_loss": "mandatory",
            "break_even": "mandatory_after_defined_favorable_move",
            "partial_take_profit": "mandatory_policy",
            "hold_loser_as_spot": "forbidden",
            "unlock_requirements": [
                "Isolated paper-margin accounting and liquidation model.",
                "Mandatory server-side stop loss before order acceptance.",
                "Auditable break-even and partial-take-profit state machine.",
                "Futures-specific backtests including fees, funding and slippage.",
                "Exchange permissions, kill switch and adapter security review.",
            ],
        },
        "risk_context": {
            "kill_switch_active": bool(kill_switch.get("active", True)),
            "max_position_pct": limits.get("max_position_pct"),
            "max_daily_loss_pct": limits.get("max_daily_loss_pct"),
            "max_drawdown_pct": limits.get("max_drawdown_pct"),
        },
        "live_execution": "blocked",
    }
