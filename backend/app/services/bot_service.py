from __future__ import annotations

from datetime import datetime, timezone

from backend.app.analytics.backtest import run_backtest
from backend.app.services.candle_service import get_candles
from backend.app.services.feature_service import build_features_from_candles
from backend.app.strategies.contracts import compile_strategy
from backend.app.storage.backtests import get_backtest, list_backtests, save_backtest_run
from backend.app.storage.bots import create_bot, create_bot_version, get_bot, list_bots
from backend.app.storage.features import latest_asset_features


FEATURE_WARMUP_BARS = 20
OPEN_CANDLE_BUFFER = 1


def list_saved_bots(limit: int = 100) -> dict:
    return list_bots(limit=limit)


def create_saved_bot(payload: dict) -> dict:
    return create_bot(payload=payload)


def get_saved_bot(bot_id: int) -> dict:
    return get_bot(bot_id=bot_id)


def create_saved_bot_version(bot_id: int, payload: dict) -> dict:
    return create_bot_version(bot_id=bot_id, payload=payload)


def feature_rows_with_close(symbol: str, timeframe: str, limit: int) -> tuple[list[dict], dict]:
    candle_limit = min(1000, limit + FEATURE_WARMUP_BARS + OPEN_CANDLE_BUFFER)
    candle_payload = get_candles(symbol=symbol, interval=timeframe, limit=candle_limit)
    candles = candle_payload["candles"]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    closed_candles = [
        candle
        for candle in candles
        if int(candle.get("close_time") or candle["timestamp"]) <= now_ms
    ]
    if candle_payload.get("served_from") == "sqlite_cache" and len(closed_candles) >= 40:
        build_features_from_candles(symbol=symbol, timeframe=timeframe, limit=candle_limit)

    features = latest_asset_features(
        symbol=symbol,
        timeframe=timeframe,
        limit=min(1000, limit + OPEN_CANDLE_BUFFER),
    )
    candles_by_timestamp = {int(candle["timestamp"]): candle for candle in closed_candles}
    rows = []
    for feature in features:
        timestamp = int(feature["timestamp"])
        candle = candles_by_timestamp.get(timestamp)
        if candle is None:
            continue
        rows.append(
            {
                **feature,
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "close_time": int(candle.get("close_time") or timestamp),
            }
        )
    rows = rows[-limit:]
    return rows, {
        "source": candle_payload.get("source"),
        "served_from": candle_payload.get("served_from"),
        "candles_requested": candle_limit,
        "feature_warmup_bars": FEATURE_WARMUP_BARS,
        "candles_received": len(candles),
        "candles_closed": len(closed_candles),
        "open_candles_excluded": len(candles) - len(closed_candles),
    }


def run_saved_bot_backtest(
    bot_id: int,
    version_id: int | None = None,
    initial_equity: float = 10_000,
    fee_pct: float = 0.1,
    slippage_pct: float = 0.05,
    limit: int = 500,
) -> dict:
    detail = get_bot(bot_id=bot_id)
    bot = detail["bot"]
    versions = detail["versions"]
    selected_version = None
    if version_id:
        selected_version = next((version for version in versions if version["id"] == version_id), None)
    else:
        selected_version = versions[0] if versions else None
    if not selected_version:
        raise ValueError("Bot version not found")
    contract = selected_version.get("contract") or compile_strategy(selected_version.get("strategy"))
    if contract.get("status") != "valid" or not contract.get("capabilities", {}).get("backtest"):
        raise ValueError("Bot version does not have a valid backtest strategy contract")

    rows, data_context = feature_rows_with_close(
        symbol=bot["base_symbol"],
        timeframe=bot["timeframe"],
        limit=limit,
    )
    available_fields = set().union(*(row.keys() for row in rows)) if rows else set()
    missing_fields = sorted(set(contract.get("required_fields") or []) - available_fields)
    if missing_fields:
        raise ValueError(f"Strategy requires unavailable feature fields: {', '.join(missing_fields)}")
    result = run_backtest(
        bot=bot,
        version=selected_version,
        rows=rows,
        initial_equity=initial_equity,
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
        requested_limit=limit,
    )
    result["data_quality"].update(data_context)
    result["metrics"]["strategy_contract_version"] = contract["contract_version"]
    result["metrics"]["strategy_hash"] = contract["strategy_hash"]
    result["metrics"]["data_quality"] = result["data_quality"]
    if data_context["open_candles_excluded"]:
        result["warnings"].append(
            {
                "code": "OPEN_CANDLES_EXCLUDED",
                "message": f"Excluded {data_context['open_candles_excluded']} candle(s) that were not closed.",
                "severity": "info",
            }
        )
    backtest_id = save_backtest_run(result)
    return {"backtest_id": backtest_id, **get_backtest(backtest_id)}


def list_saved_bot_backtests(bot_id: int | None = None, limit: int = 100) -> dict:
    return list_backtests(bot_id=bot_id, limit=limit)


def get_saved_bot_backtest(backtest_id: int) -> dict:
    return get_backtest(backtest_id=backtest_id)
