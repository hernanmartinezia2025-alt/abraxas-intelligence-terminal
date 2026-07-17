from __future__ import annotations

from math import sqrt
from statistics import median

from backend.app.analytics.spot_analysis import adx_value, squeeze_momentum


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _z_score(value: float, values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    average = _mean(values)
    deviation = sqrt(sum((item - average) ** 2 for item in values) / (len(values) - 1))
    return (value - average) / deviation if deviation else None


def detect_sweep(candles: list[dict], swing_lookback: int = 20, volume_lookback: int = 30) -> dict:
    """Detect a reclaimed prior extreme on the last *closed* candle supplied by the caller."""
    minimum = max(swing_lookback + 1, volume_lookback + 1, 45)
    if len(candles) < minimum:
        return {
            "direction": "none",
            "qualified": False,
            "reason": f"At least {minimum} closed candles are required.",
            "required_candles": minimum,
            "available_candles": len(candles),
        }

    candle = candles[-1]
    prior = candles[-swing_lookback - 1:-1]
    prior_low = min(float(item["low"]) for item in prior)
    prior_high = max(float(item["high"]) for item in prior)
    open_price = float(candle["open"])
    high = float(candle["high"])
    low = float(candle["low"])
    close = float(candle["close"])
    candle_range = max(high - low, 0.0)
    lower_wick = max(min(open_price, close) - low, 0.0)
    upper_wick = max(high - max(open_price, close), 0.0)
    bullish_reclaim = low < prior_low and close > prior_low
    bearish_reclaim = high > prior_high and close < prior_high

    if bullish_reclaim and not bearish_reclaim:
        direction = "bullish_reversal"
        swept_level = prior_low
        wick_share = lower_wick / candle_range if candle_range else 0.0
        excursion_pct = (prior_low / low - 1) * 100 if low else None
    elif bearish_reclaim and not bullish_reclaim:
        direction = "bearish_reversal"
        swept_level = prior_high
        wick_share = upper_wick / candle_range if candle_range else 0.0
        excursion_pct = (high / prior_high - 1) * 100 if prior_high else None
    else:
        direction = "none"
        swept_level = None
        wick_share = max(lower_wick, upper_wick) / candle_range if candle_range else 0.0
        excursion_pct = None

    historical_volumes = [float(item.get("volume") or 0) for item in candles[-volume_lookback - 1:-1]]
    volume = float(candle.get("volume") or 0)
    volume_z = _z_score(volume, historical_volumes)
    long_wick = wick_share >= 0.35
    volume_spike = volume_z is not None and volume_z >= 1.5
    qualified = direction != "none" and long_wick and volume_spike

    return {
        "direction": direction,
        "qualified": qualified,
        "reason": (
            "Prior extreme reclaimed with long wick and elevated closed-candle volume."
            if qualified
            else "No closed-candle sweep satisfies reclaim, wick and volume thresholds."
        ),
        "candle_timestamp": int(candle["timestamp"]),
        "candle_close_time": int(candle.get("close_time") or candle["timestamp"]),
        "close": close,
        "extreme": low if direction == "bullish_reversal" else high if direction == "bearish_reversal" else None,
        "swept_level": swept_level,
        "prior_swing_low": prior_low,
        "prior_swing_high": prior_high,
        "wick_share": wick_share,
        "wick_threshold": 0.35,
        "volume": volume,
        "volume_z_score": volume_z,
        "volume_z_threshold": 1.5,
        "excursion_pct": excursion_pct,
        "checks": {
            "reclaimed_prior_extreme": direction != "none",
            "long_wick": long_wick,
            "closed_candle_volume_spike": volume_spike,
        },
    }


def analyze_depth(order_book: dict | None, direction: str, entry: float) -> dict:
    if not order_book:
        return {
            "available": False,
            "target_wall": None,
            "target_price": None,
            "warning": "Current depth snapshot unavailable; no wall target can be calculated.",
        }
    side_name = "asks" if direction == "bullish_reversal" else "bids"
    levels = [item for item in order_book.get(side_name, []) if float(item.get("notional") or 0) > 0]
    baseline = median([float(item["notional"]) for item in levels]) if levels else 0.0
    significant = [item for item in levels if baseline and float(item["notional"]) >= baseline * 3]
    valid = [
        item for item in significant
        if (direction == "bullish_reversal" and float(item["price"]) > entry)
        or (direction == "bearish_reversal" and float(item["price"]) < entry)
    ]
    wall = valid[0] if valid else None
    target = None
    if wall:
        target = float(wall["price"]) * (0.995 if direction == "bullish_reversal" else 1.005)
        if (direction == "bullish_reversal" and target <= entry) or (
            direction == "bearish_reversal" and target >= entry
        ):
            target = None
    return {
        "available": True,
        "source": order_book.get("source"),
        "fetched_at": order_book.get("fetched_at"),
        "best_bid": order_book.get("best_bid"),
        "best_ask": order_book.get("best_ask"),
        "spread_percent": order_book.get("spread_percent"),
        "wall_threshold_multiple": 3.0,
        "target_wall": wall,
        "target_price": target,
        "front_run_pct": 0.5,
        "warning": "Single current L2 snapshot; it does not prove wall persistence or historical absorption.",
    }


def analyze_aggregate_trade_flow(trades: list[dict] | None, direction: str) -> dict:
    if not trades:
        return {
            "available": False,
            "confirmed": False,
            "trade_count": 0,
            "warning": "No aggregate trades are available for the closed-candle window.",
        }
    ordered = sorted(trades, key=lambda item: (int(item["event_time"]), int(item["aggregate_trade_id"])))
    buy_notional = sum(float(item["quote_quantity"]) for item in ordered if item["aggressor_side"] == "buy")
    sell_notional = sum(float(item["quote_quantity"]) for item in ordered if item["aggressor_side"] == "sell")
    total_notional = buy_notional + sell_notional
    delta = buy_notional - sell_notional
    coverage_complete = len(ordered) < 1000

    if direction == "bullish_reversal":
        extreme_index = min(range(len(ordered)), key=lambda index: float(ordered[index]["price"]))
        impulse_notional = sell_notional
        impulse_share = sell_notional / total_notional if total_notional else 0.0
        expected_reversal = "buy"
    elif direction == "bearish_reversal":
        extreme_index = max(range(len(ordered)), key=lambda index: float(ordered[index]["price"]))
        impulse_notional = buy_notional
        impulse_share = buy_notional / total_notional if total_notional else 0.0
        expected_reversal = "sell"
    else:
        extreme_index = len(ordered) - 1
        impulse_notional = 0.0
        impulse_share = 0.0
        expected_reversal = "none"

    after_extreme = ordered[extreme_index + 1:]
    post_buy = sum(float(item["quote_quantity"]) for item in after_extreme if item["aggressor_side"] == "buy")
    post_sell = sum(float(item["quote_quantity"]) for item in after_extreme if item["aggressor_side"] == "sell")
    post_delta = post_buy - post_sell
    reversal_aligned = (
        direction == "bullish_reversal" and post_delta > 0
    ) or (
        direction == "bearish_reversal" and post_delta < 0
    )
    confirmed = (
        coverage_complete
        and direction != "none"
        and impulse_share >= 0.55
        and len(after_extreme) >= 5
        and reversal_aligned
    )
    return {
        "available": True,
        "confirmed": confirmed,
        "source": "binance_agg_trades_rest",
        "trade_count": len(ordered),
        "coverage": "complete_under_limit" if coverage_complete else "possibly_truncated_at_1000",
        "first_event_time": int(ordered[0]["event_time"]),
        "last_event_time": int(ordered[-1]["event_time"]),
        "buy_notional": buy_notional,
        "sell_notional": sell_notional,
        "delta_notional": delta,
        "imbalance_pct": delta / total_notional * 100 if total_notional else 0.0,
        "impulse_notional": impulse_notional,
        "impulse_side_share": impulse_share,
        "impulse_share_threshold": 0.55,
        "extreme_trade_price": float(ordered[extreme_index]["price"]),
        "extreme_trade_time": int(ordered[extreme_index]["event_time"]),
        "trades_after_extreme": len(after_extreme),
        "post_extreme_delta_notional": post_delta,
        "expected_reversal_side": expected_reversal,
        "reversal_aligned": reversal_aligned,
        "warning": "Aggregate REST trades expose aggressor-side evidence, not trader identity, stop orders or liquidation intent.",
    }


def build_liquidity_sweep_evaluation(
    candles: list[dict],
    order_book: dict | None,
    aggregate_trades: list[dict] | None,
    microstructure_status: dict | None,
    symbol: str,
    timeframe: str,
    account_equity: float = 10_000,
    risk_pct: float = 0.5,
) -> dict:
    sweep = detect_sweep(candles)
    direction = sweep["direction"]
    squeeze = squeeze_momentum(candles) if len(candles) >= 40 else {"direction": "unavailable"}
    adx = adx_value(candles)
    previous_adx = adx_value(candles[:-1])
    expected_turn = "long_turn" if direction == "bullish_reversal" else "short_turn"
    squeeze_passed = direction != "none" and squeeze.get("direction") == expected_turn
    adx_passed = adx is not None and previous_adx is not None and adx < previous_adx
    technical_confirmed = squeeze_passed and adx_passed
    entry = float(sweep.get("close") or candles[-1]["close"])
    depth = analyze_depth(order_book, direction, entry) if direction != "none" else analyze_depth(order_book, "bullish_reversal", entry)
    trade_flow = analyze_aggregate_trade_flow(aggregate_trades, direction)

    risk_plan = None
    if sweep.get("qualified") and sweep.get("extreme") is not None:
        extreme = float(sweep["extreme"])
        stop = extreme * (0.9995 if direction == "bullish_reversal" else 1.0005)
        stop_distance = abs(entry - stop)
        risk_budget = account_equity * risk_pct / 100
        quantity = risk_budget / stop_distance if stop_distance > 0 else None
        target = depth.get("target_price")
        reward = abs(float(target) - entry) if target is not None else None
        risk_plan = {
            "status": "observation_only_locked",
            "entry_reference": entry,
            "structural_stop": stop,
            "target": target,
            "risk_budget": risk_budget,
            "risk_pct": risk_pct,
            "quantity": quantity,
            "notional": quantity * entry if quantity is not None else None,
            "reward_risk": reward / stop_distance if reward is not None and stop_distance else None,
            "short_supported": direction != "bearish_reversal",
        }

    if not sweep.get("checks", {}).get("reclaimed_prior_extreme"):
        state = "scanning"
    elif not sweep.get("qualified"):
        state = "sweep_unconfirmed"
    elif not trade_flow.get("confirmed"):
        state = "flow_pending"
    elif not technical_confirmed:
        state = "exhaustion_pending"
    elif depth.get("target_price") is None:
        state = "target_pending"
    else:
        state = "observation_candidate"

    return {
        "contract": "liquidity_sweep_observer_v2",
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "state": state,
        "direction": direction,
        "order_allowed": False,
        "execution_performed": False,
        "claim_boundary": "This detects an observable liquidity-sweep pattern. It cannot identify actors or prove stop-loss hunting intent.",
        "capabilities": {
            "closed_ohlcv": {"status": "available", "source": "Binance + SQLite cache"},
            "squeeze_adx": {"status": "available", "source": "ABRAXAS deterministic analytics"},
            "current_l2_snapshot": {"status": "available" if order_book else "degraded", "source": "Binance Depth"},
            "closed_candle_aggregate_trade_flow": {
                "status": "available" if trade_flow.get("available") else "degraded",
                "source": "Binance aggregate trades persisted from REST/WebSocket",
            },
            "persisted_l2_snapshots": {
                "status": "available" if (microstructure_status or {}).get("order_book_snapshots", {}).get("row_count", 0) else "collecting",
                "snapshot_count": (microstructure_status or {}).get("order_book_snapshots", {}).get("row_count", 0),
            },
            "realtime_trade_flow": {
                "status": "available" if (microstructure_status or {}).get("continuous_stream") else "inactive",
                "reason": "Public WebSocket aggTrades persist while the audited collector is running.",
            },
            "continuous_l2_deltas": {
                "status": "available" if (microstructure_status or {}).get("continuous_stream") else "inactive",
                "delta_count": (microstructure_status or {}).get("order_book_deltas", {}).get("row_count", 0),
                "reason": "Binance update IDs are sequence-validated before persistence.",
            },
            "historical_l2": {
                "status": "available" if (microstructure_status or {}).get("historical_l2_ready") else "collecting",
                "reason": "Deltas are accumulating; deterministic point-in-time replay is the next gate.",
            },
            "liquidation_clusters": {"status": "missing", "reason": "No liquidation feed is integrated."},
        },
        "evidence": {
            "sweep": sweep,
            "exhaustion": {
                "confirmed": technical_confirmed,
                "squeeze_passed": squeeze_passed,
                "squeeze": squeeze,
                "adx_passed": adx_passed,
                "adx": adx,
                "previous_adx": previous_adx,
                "adx_slope": "falling" if adx_passed else "rising_flat_or_unavailable",
            },
            "depth": depth,
            "trade_flow": trade_flow,
        },
        "risk_plan": risk_plan,
        "state_machine": [
            {"state": "scanning", "label": "Targeting", "reachable": True},
            {"state": "sweep_unconfirmed", "label": "Wick observed", "reachable": True},
            {"state": "flow_pending", "label": "Aggressor flow", "reachable": True},
            {"state": "exhaustion_pending", "label": "Exhaustion", "reachable": True},
            {"state": "observation_candidate", "label": "Risk plan", "reachable": True},
            {"state": "executing", "label": "Execution", "reachable": False, "reason": "Live execution is locked by design."},
        ],
    }
