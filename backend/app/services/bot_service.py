from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.analytics.backtest import run_backtest
from backend.app.services.candle_service import get_candles
from backend.app.services.feature_service import build_features_from_candles
from backend.app.strategies.contracts import compile_strategy
from backend.app.storage.backtests import get_backtest, list_backtests, save_backtest_run
from backend.app.storage.bots import create_bot, create_bot_version, get_bot, list_bots
from backend.app.storage.features import latest_asset_features
from backend.app.storage.signals import get_signal_evaluation, list_signal_evaluations, save_signal_evaluation
from backend.app.storage.paper import account_snapshot, get_position_allocation, latest_price, latest_price_record, place_market_order, recovered_execution_result
from backend.app.storage.proposals import claim_paper_proposal, dismiss_paper_proposal, get_paper_proposal, list_paper_proposals, mark_paper_proposal_submitted, release_paper_proposal_claim, save_paper_proposal
from backend.app.storage.sqlite import connect
from backend.app.storage.execution import get_execution_intent
from backend.app.strategies.runtime import evaluate_position_protection, evaluate_strategy
from backend.app.market.freshness import PROPOSAL_TTL_SECONDS, MAX_PRICE_DRIFT_PCT, parse_timestamp, utc_now, validate_feature_freshness, validate_price_freshness


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


def evaluate_saved_bot_signal(bot_id: int, version_id: int | None = None) -> dict:
    detail = get_bot(bot_id=bot_id)
    bot = detail["bot"]
    versions = detail["versions"]
    version = next((item for item in versions if item["id"] == version_id), None) if version_id else (versions[0] if versions else None)
    if not version:
        raise ValueError("Bot version not found")
    contract = version.get("contract") or compile_strategy(version.get("strategy"))
    if contract.get("status") != "valid":
        raise ValueError("Bot version does not have a valid strategy contract")
    features = latest_asset_features(symbol=bot["base_symbol"], timeframe=bot["timeframe"], limit=1)
    if not features:
        raise ValueError("No persisted asset features available for this bot")
    feature = features[0]
    freshness = validate_feature_freshness(int(feature["timestamp"]), bot["timeframe"])
    missing = sorted(set(contract.get("required_fields") or []) - set(feature))
    if missing:
        raise ValueError(f"Strategy requires unavailable feature fields: {', '.join(missing)}")
    evaluation = evaluate_strategy(contract, feature)
    with connect() as connection:
        price_record = latest_price_record(connection, bot["base_symbol"])
    price_freshness = validate_price_freshness(price_record["timestamp"])
    allocation = get_position_allocation(bot["base_symbol"], bot_id, version["id"], contract["strategy_hash"])
    protection = evaluate_position_protection(allocation, price_record["price"], version["strategy"]["risk"])
    position_return_pct = protection["position_return_pct"]
    trigger_reason = "strategy_exit" if evaluation["signal"] == "exit_candidate" else None
    if protection["trigger_reason"]:
        trigger_reason = protection["trigger_reason"]
        evaluation["signal"] = "exit_candidate"
        evaluation["exit_passed"] = True
        evaluation["conflict"] = False
        evaluation["trace"]["protection"] = [{"trigger": trigger_reason, **protection["trace"]}]
    return save_signal_evaluation({
        **evaluation,
        "bot_id": bot_id,
        "bot_version_id": version["id"],
        "strategy_hash": contract["strategy_hash"],
        "symbol": bot["base_symbol"],
        "timeframe": bot["timeframe"],
        "feature_timestamp": feature["timestamp"],
        "features": {**{field: feature.get(field) for field in contract["required_fields"]}, "_freshness": freshness, "_price_freshness": price_freshness},
        "trigger_reason": trigger_reason,
        "price_timestamp": price_record["timestamp"],
        "position_return_pct": position_return_pct,
    })


def list_saved_bot_signals(bot_id: int, limit: int = 50) -> dict:
    get_bot(bot_id=bot_id)
    return list_signal_evaluations(bot_id=bot_id, limit=limit)


def create_saved_bot_paper_proposal(bot_id: int, evaluation_id: int) -> dict:
    detail = get_bot(bot_id=bot_id)
    evaluation = get_signal_evaluation(evaluation_id)
    if evaluation["bot_id"] != bot_id:
        raise ValueError("Signal evaluation does not belong to this bot")
    if evaluation["signal"] not in {"entry_candidate", "exit_candidate"}:
        raise ValueError("Only entry_candidate or exit_candidate signals can create paper proposals")
    version = next((item for item in detail["versions"] if item["id"] == evaluation["bot_version_id"]), None)
    if not version or version.get("strategy_hash") != evaluation["strategy_hash"]:
        raise ValueError("Signal strategy fingerprint no longer matches its bot version")
    snapshot = account_snapshot()
    with connect() as connection:
        price_record = latest_price_record(connection, evaluation["symbol"])
    validate_price_freshness(price_record["timestamp"])
    price = price_record["price"]
    position_pct = float(version["strategy"]["risk"]["max_position_pct"])
    allocation = get_position_allocation(evaluation["symbol"], bot_id, evaluation["bot_version_id"], evaluation["strategy_hash"])
    if evaluation["signal"] == "exit_candidate":
        if not allocation or float(allocation["quantity"]) <= 0:
            raise ValueError("Exit candidate has no open position allocation for this bot version")
        action = "sell"
        quantity = round(float(allocation["quantity"]), 8)
        reason = f"Exit candidate #{evaluation_id}; close allocation #{allocation['id']} revision {allocation['revision']}."
    else:
        action = "buy"
        current_notional = float(allocation["quantity"]) * price if allocation else 0.0
        target_notional = min(float(snapshot["equity"]) * position_pct / 100, float(snapshot["account"]["cash_balance"]) / 1.001)
        quantity = round(max(0.0, target_notional - current_notional) / price, 8)
        reason = f"Entry candidate #{evaluation_id}; target allocation {position_pct:.2f}% of paper equity."
    if quantity <= 0:
        raise ValueError("Paper account has no available quantity or capital for this proposal")
    expires_at = (utc_now() + timedelta(seconds=PROPOSAL_TTL_SECONDS)).isoformat()
    return save_paper_proposal({
        "signal_evaluation_id": evaluation_id,
        "bot_id": bot_id,
        "bot_version_id": evaluation["bot_version_id"],
        "symbol": evaluation["symbol"],
        "action": action,
        "quantity": quantity,
        "reference_price": price,
        "proposed_notional": round(quantity * price, 8),
        "reason": reason,
        "strategy_hash": evaluation["strategy_hash"],
        "price_timestamp": price_record["timestamp"],
        "expires_at": expires_at,
        "allocation_id": allocation["id"] if allocation else None,
        "allocation_revision": allocation["revision"] if allocation else None,
        "trigger_reason": evaluation.get("trigger_reason") or evaluation["signal"],
    })


def list_saved_bot_paper_proposals(bot_id: int, limit: int = 50) -> dict:
    get_bot(bot_id=bot_id)
    return list_paper_proposals(bot_id=bot_id, limit=limit)


def dismiss_saved_bot_paper_proposal(bot_id: int, proposal_id: int) -> dict:
    get_bot(bot_id=bot_id)
    return dismiss_paper_proposal(proposal_id=proposal_id, bot_id=bot_id)


def submit_saved_bot_paper_proposal(bot_id: int, proposal_id: int) -> dict:
    get_bot(bot_id=bot_id)
    existing_proposal = get_paper_proposal(proposal_id)
    if int(existing_proposal["bot_id"]) != bot_id:
        raise ValueError("Paper proposal does not belong to this bot")
    intent_id = f"paper-proposal-{proposal_id}"
    existing_intent = get_execution_intent(intent_id)
    if existing_proposal["status"] == "submitted":
        recovered = recovered_execution_result(existing_intent) if existing_intent else {"status": "submitted", "recovered": True}
        return {"proposal": existing_proposal, "paper_result": recovered, "live_execution": "blocked"}
    if existing_intent and existing_intent["status"] in {"filled", "rejected", "failed"}:
        recovered = recovered_execution_result(existing_intent)
        updated = mark_paper_proposal_submitted(proposal_id=proposal_id, bot_id=bot_id, result=recovered)
        return {"proposal": updated, "paper_result": recovered, "live_execution": "blocked"}
    if existing_proposal.get("expires_at") and parse_timestamp(existing_proposal["expires_at"]) < utc_now():
        raise ValueError("Paper proposal expired before confirmation")
    with connect() as connection:
        current_price = latest_price_record(connection, existing_proposal["symbol"])
    validate_price_freshness(current_price["timestamp"])
    price_drift_pct = abs((current_price["price"] / float(existing_proposal["reference_price"])) - 1) * 100
    if price_drift_pct > MAX_PRICE_DRIFT_PCT:
        raise ValueError(f"Paper proposal price drift {price_drift_pct:.2f}% exceeds {MAX_PRICE_DRIFT_PCT:.2f}%")
    if existing_proposal["action"] == "sell":
        allocation = get_position_allocation(
            existing_proposal["symbol"], bot_id, existing_proposal["bot_version_id"], existing_proposal["strategy_hash"]
        )
        if not allocation or allocation["id"] != existing_proposal.get("allocation_id") or allocation["revision"] != existing_proposal.get("allocation_revision"):
            raise ValueError("Paper exit proposal allocation changed after creation")
        if abs(float(allocation["quantity"]) - float(existing_proposal["quantity"])) > 1e-8:
            raise ValueError("Paper exit proposal quantity no longer matches its allocation")
    proposal = claim_paper_proposal(proposal_id=proposal_id, bot_id=bot_id)
    claim_token = proposal["_claim_token"]
    evaluation = get_signal_evaluation(proposal["signal_evaluation_id"])
    try:
        result = place_market_order({
            "symbol": proposal["symbol"],
            "side": proposal["action"],
            "quantity": proposal["quantity"],
            "bot_id": bot_id,
            "bot_version_id": proposal["bot_version_id"],
            "strategy_hash": evaluation["strategy_hash"],
            "signal_evaluation_id": proposal["signal_evaluation_id"],
            "proposal_id": proposal_id,
        })
    except Exception as exc:
        release_paper_proposal_claim(proposal_id, claim_token, str(exc))
        raise
    updated = mark_paper_proposal_submitted(proposal_id=proposal_id, bot_id=bot_id, result=result, claim_token=claim_token)
    return {"proposal": updated, "paper_result": result, "live_execution": "blocked"}
