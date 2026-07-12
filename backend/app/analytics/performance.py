from __future__ import annotations

import math
import statistics


PERIODS_PER_YEAR = {
    "1m": 365 * 24 * 60,
    "5m": 365 * 24 * 12,
    "15m": 365 * 24 * 4,
    "1h": 365 * 24,
    "4h": 365 * 6,
    "1d": 365,
}


def _finite(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def calculate_performance_metrics(equity_curve: list[dict], timeframe: str) -> dict:
    equities = [float(point["equity"]) for point in equity_curve if float(point.get("equity") or 0) > 0]
    if len(equities) < 2:
        return {"status": "insufficient_data", "period_samples": 0, "methodology": "period_returns"}

    returns = [(current / previous) - 1 for previous, current in zip(equities, equities[1:]) if previous]
    periods_per_year = PERIODS_PER_YEAR.get(timeframe, 365)
    mean_return = statistics.fmean(returns)
    volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
    downside = [min(value, 0.0) for value in returns]
    downside_deviation = math.sqrt(statistics.fmean(value * value for value in downside)) if downside else 0.0
    sharpe = (mean_return / volatility) * math.sqrt(periods_per_year) if volatility else None
    sortino = (mean_return / downside_deviation) * math.sqrt(periods_per_year) if downside_deviation else None

    timestamps = [int(point["timestamp"]) for point in equity_curve if point.get("timestamp") is not None]
    span_days = ((max(timestamps) - min(timestamps)) / 86_400_000) if len(timestamps) > 1 else 0.0
    total_return = (equities[-1] / equities[0]) - 1
    cagr = None
    if span_days > 0:
        try:
            cagr = (equities[-1] / equities[0]) ** (365 / span_days) - 1
        except OverflowError:
            cagr = None

    drawdowns = []
    peak = equities[0]
    for equity in equities:
        peak = max(peak, equity)
        drawdowns.append((equity / peak) - 1 if peak else 0.0)
    max_drawdown = abs(min(drawdowns))
    ulcer_index = math.sqrt(statistics.fmean(value * value for value in drawdowns)) * 100
    calmar = cagr / max_drawdown if cagr is not None and max_drawdown else None
    recovery = total_return / max_drawdown if max_drawdown else None

    ordered_returns = sorted(returns)
    tail_count = max(1, math.ceil(len(ordered_returns) * 0.05))
    var_95 = ordered_returns[tail_count - 1] * 100
    cvar_95 = statistics.fmean(ordered_returns[:tail_count]) * 100
    positive_periods = sum(value > 0 for value in returns)

    return {
        "status": "ready",
        "methodology": "period_returns",
        "timeframe": timeframe,
        "period_samples": len(returns),
        "periods_per_year": periods_per_year,
        "span_days": _finite(span_days, 2),
        "period_win_rate_pct": _finite((positive_periods / len(returns)) * 100),
        "annualized_volatility_pct": _finite(volatility * math.sqrt(periods_per_year) * 100),
        "sharpe_ratio": _finite(sharpe),
        "sortino_ratio": _finite(sortino),
        "cagr_pct": _finite(cagr * 100 if cagr is not None else None),
        "calmar_ratio": _finite(calmar),
        "ulcer_index_pct": _finite(ulcer_index),
        "recovery_factor": _finite(recovery),
        "period_var_95_pct": _finite(var_95),
        "period_cvar_95_pct": _finite(cvar_95),
    }
