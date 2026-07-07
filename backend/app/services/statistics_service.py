from __future__ import annotations

from backend.app.analytics.statistics import run_monte_carlo, summarize_statistics
from backend.app.services.candle_service import get_candles
from backend.app.storage.statistics_runs import list_statistics_runs, save_statistics_run


def get_statistics(symbol: str, interval: str, limit: int, horizon_steps: int, paths: int) -> dict:
    candle_payload = get_candles(symbol=symbol, interval=interval, limit=limit)
    candles = candle_payload["candles"]
    summary = summarize_statistics(symbol=symbol, interval=interval, candles=candles)
    monte_carlo = run_monte_carlo(
        symbol=symbol,
        interval=interval,
        candles=candles,
        horizon_steps=horizon_steps,
        paths=paths,
    )
    run_id = save_statistics_run(
        symbol=symbol,
        timeframe=interval,
        run_type="full_statistics",
        metrics={
            "summary": summary,
            "monte_carlo": monte_carlo,
            "data_source": candle_payload["served_from"],
        },
        candles=candles,
    )
    return {
        "data_source": candle_payload["served_from"],
        "statistics_run_id": run_id,
        "summary": summary,
        "monte_carlo": monte_carlo,
    }


def get_statistics_summary(symbol: str, interval: str, limit: int) -> dict:
    candles = get_candles(symbol=symbol, interval=interval, limit=limit)["candles"]
    summary = summarize_statistics(symbol=symbol, interval=interval, candles=candles)
    run_id = save_statistics_run(
        symbol=symbol,
        timeframe=interval,
        run_type="summary",
        metrics=summary,
        candles=candles,
    )
    return {**summary, "statistics_run_id": run_id}


def get_monte_carlo(symbol: str, interval: str, limit: int, horizon_steps: int, paths: int) -> dict:
    candles = get_candles(symbol=symbol, interval=interval, limit=limit)["candles"]
    monte_carlo = run_monte_carlo(
        symbol=symbol,
        interval=interval,
        candles=candles,
        horizon_steps=horizon_steps,
        paths=paths,
    )
    run_id = save_statistics_run(
        symbol=symbol,
        timeframe=interval,
        run_type="monte_carlo",
        metrics=monte_carlo,
        candles=candles,
    )
    return {**monte_carlo, "statistics_run_id": run_id}


def get_statistics_runs(
    symbol: str | None = None,
    timeframe: str | None = None,
    run_type: str | None = None,
    limit: int = 100,
) -> dict:
    return {
        "symbol": symbol.upper() if symbol else None,
        "timeframe": timeframe,
        "run_type": run_type,
        "limit": limit,
        "runs": list_statistics_runs(symbol=symbol, timeframe=timeframe, run_type=run_type, limit=limit),
    }
