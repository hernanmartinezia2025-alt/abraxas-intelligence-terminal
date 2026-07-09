from __future__ import annotations

from backend.app.analytics.backtest import run_backtest
from backend.app.services.candle_service import get_candles
from backend.app.services.feature_service import build_features_from_candles
from backend.app.storage.backtests import get_backtest, list_backtests, save_backtest_run
from backend.app.storage.bots import create_bot, create_bot_version, get_bot, list_bots
from backend.app.storage.features import latest_asset_features


def list_saved_bots(limit: int = 100) -> dict:
    return list_bots(limit=limit)


def create_saved_bot(payload: dict) -> dict:
    return create_bot(payload=payload)


def get_saved_bot(bot_id: int) -> dict:
    return get_bot(bot_id=bot_id)


def create_saved_bot_version(bot_id: int, payload: dict) -> dict:
    return create_bot_version(bot_id=bot_id, payload=payload)


def feature_rows_with_close(symbol: str, timeframe: str, limit: int) -> list[dict]:
    candle_payload = get_candles(symbol=symbol, interval=timeframe, limit=limit)
    candles = candle_payload["candles"]
    if len(candles) >= 40:
        build_features_from_candles(symbol=symbol, timeframe=timeframe, limit=limit)

    features = latest_asset_features(symbol=symbol, timeframe=timeframe, limit=limit)
    close_by_timestamp = {int(candle["timestamp"]): float(candle["close"]) for candle in candles}
    rows = []
    for feature in features:
        timestamp = int(feature["timestamp"])
        close = close_by_timestamp.get(timestamp)
        if close is None:
            continue
        rows.append({**feature, "close": close})
    return rows


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

    rows = feature_rows_with_close(symbol=bot["base_symbol"], timeframe=bot["timeframe"], limit=limit)
    result = run_backtest(
        bot=bot,
        version=selected_version,
        rows=rows,
        initial_equity=initial_equity,
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
    )
    backtest_id = save_backtest_run(result)
    return {"backtest_id": backtest_id, **get_backtest(backtest_id)}


def list_saved_bot_backtests(bot_id: int | None = None, limit: int = 100) -> dict:
    return list_backtests(bot_id=bot_id, limit=limit)


def get_saved_bot_backtest(backtest_id: int) -> dict:
    return get_backtest(backtest_id=backtest_id)
