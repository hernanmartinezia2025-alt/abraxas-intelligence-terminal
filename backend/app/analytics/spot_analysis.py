from __future__ import annotations

from math import sqrt


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def standard_deviation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    average = mean(values)
    return sqrt(sum((value - average) ** 2 for value in values) / (len(values) - 1))


def moving_average(closes: list[float], period: int) -> float | None:
    return mean(closes[-period:]) if len(closes) >= period else None


def exponential_moving_average(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    result = mean(values[:period])
    multiplier = 2 / (period + 1)
    for value in values[period:]:
        result = value * multiplier + result * (1 - multiplier)
    return result


def linear_regression_last(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    sample = values[-period:]
    x_average = (period - 1) / 2
    y_average = mean(sample)
    denominator = sum((index - x_average) ** 2 for index in range(period))
    slope = sum((index - x_average) * (value - y_average) for index, value in enumerate(sample)) / denominator
    intercept = y_average - slope * x_average
    return intercept + slope * (period - 1)


def true_ranges(candles: list[dict]) -> list[float]:
    ranges = []
    for index, candle in enumerate(candles):
        high = float(candle["high"])
        low = float(candle["low"])
        previous_close = float(candles[index - 1]["close"]) if index else float(candle["open"])
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return ranges


def adx_value(candles: list[dict], period: int = 14) -> float | None:
    """Return Wilder ADX, using only closed candles supplied by the caller."""
    if len(candles) < period * 2:
        return None
    tr = true_ranges(candles)
    plus_dm = [0.0]
    minus_dm = [0.0]
    for index in range(1, len(candles)):
        up = float(candles[index]["high"]) - float(candles[index - 1]["high"])
        down = float(candles[index - 1]["low"]) - float(candles[index]["low"])
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
    smoothed_tr = sum(tr[1:period + 1])
    smoothed_plus = sum(plus_dm[1:period + 1])
    smoothed_minus = sum(minus_dm[1:period + 1])
    dx_values = []
    for index in range(period, len(candles)):
        if index > period:
            smoothed_tr = smoothed_tr - smoothed_tr / period + tr[index]
            smoothed_plus = smoothed_plus - smoothed_plus / period + plus_dm[index]
            smoothed_minus = smoothed_minus - smoothed_minus / period + minus_dm[index]
        plus_di = 100 * smoothed_plus / smoothed_tr if smoothed_tr else 0.0
        minus_di = 100 * smoothed_minus / smoothed_tr if smoothed_tr else 0.0
        total = plus_di + minus_di
        dx_values.append(100 * abs(plus_di - minus_di) / total if total else 0.0)
    if len(dx_values) < period:
        return None
    adx = mean(dx_values[:period])
    for dx in dx_values[period:]:
        adx = ((adx * (period - 1)) + dx) / period
    return adx


def squeeze_momentum(candles: list[dict], period: int = 20) -> dict:
    closes = [float(item["close"]) for item in candles]
    momentum_source = []
    for index in range(period - 1, len(candles)):
        window = candles[index - period + 1:index + 1]
        midpoint = (max(float(item["high"]) for item in window) + min(float(item["low"]) for item in window)) / 2
        baseline = (midpoint + mean([float(item["close"]) for item in window])) / 2
        momentum_source.append(float(candles[index]["close"]) - baseline)
    current = linear_regression_last(momentum_source, period)
    previous = linear_regression_last(momentum_source[:-1], period)
    close_window = closes[-period:]
    basis = mean(close_window)
    deviation = standard_deviation(close_window) or 0.0
    atr = mean(true_ranges(candles)[-period:]) or 0.0
    squeeze_on = basis - 2 * deviation > basis - 1.5 * atr and basis + 2 * deviation < basis + 1.5 * atr
    direction = "long_turn" if current is not None and previous is not None and current < 0 and current > previous else "short_turn" if current is not None and previous is not None and current > 0 and current < previous else "no_turn"
    return {"value": current, "previous": previous, "direction": direction, "squeeze_on": squeeze_on}


def approximate_volume_poc(candles: list[dict], buckets: int = 48) -> dict:
    window = candles[-120:]
    low = min(float(item["low"]) for item in window)
    high = max(float(item["high"]) for item in window)
    if high <= low:
        return {"price": low, "buckets": buckets, "method": "typical_price_volume_approximation"}
    step = (high - low) / buckets
    profile = [0.0] * buckets
    for item in window:
        typical = (float(item["high"]) + float(item["low"]) + float(item["close"])) / 3
        index = min(buckets - 1, max(0, int((typical - low) / step)))
        profile[index] += float(item.get("volume") or 0)
    poc_index = max(range(buckets), key=lambda index: profile[index])
    return {"price": low + (poc_index + 0.5) * step, "buckets": buckets, "method": "typical_price_volume_approximation"}


def trading_latino_core(candles: list[dict]) -> dict:
    closes = [float(item["close"]) for item in candles]
    close = closes[-1]
    squeeze = squeeze_momentum(candles)
    adx = adx_value(candles)
    previous_adx = adx_value(candles[:-1])
    ema10 = exponential_moving_average(closes, 10)
    ema55 = exponential_moving_average(closes, 55)
    distance_ema55_pct = abs(close / ema55 - 1) * 100 if ema55 else None
    current_low = float(candles[-1]["low"])
    poc = approximate_volume_poc(candles)
    filters = {
        "directionality": squeeze["direction"] == "long_turn",
        "adx_weakening": adx is not None and previous_adx is not None and adx < previous_adx,
        "ema55_support": (
            ema10 is not None and ema55 is not None
            and ema10 >= ema55
            and current_low <= ema55 * 1.02
            and close >= ema55 * 0.995
        ),
        "poc_support": poc["price"] <= close,
    }
    return {
        "close": close, "squeeze": squeeze, "adx": adx, "previous_adx": previous_adx,
        "ema10": ema10, "ema55": ema55, "distance_ema55_pct": distance_ema55_pct,
        "poc": poc, "filters": filters, "base_candidate": all(filters.values()),
    }


def trading_latino_five_filters(candles: list[dict]) -> dict:
    current = trading_latino_core(candles)
    consecutive = 0
    first_candidate_close = None
    for offset in range(min(8, len(candles) - 59)):
        prefix = candles[:len(candles) - offset]
        result = trading_latino_core(prefix)
        if not result["base_candidate"]:
            break
        consecutive += 1
        first_candidate_close = result["close"]
    progress_pct = (current["close"] / first_candidate_close - 1) * 100 if first_candidate_close else None
    if not current["base_candidate"]:
        time_status = "not_active"
    elif consecutive <= 3:
        time_status = "timely"
    elif progress_pct is not None and progress_pct <= 0.5:
        time_status = "expired_no_progress"
    else:
        time_status = "developing"
    time_filter = time_status in {"timely", "developing"}
    passed = sum(bool(value) for value in current["filters"].values()) + int(time_filter)
    return {
        "contract": "trading_latino_5f_v1",
        "mode": "spot_long_only_observation",
        "decision": "buy_candidate" if passed == 5 else "blocked",
        "filters_passed": passed,
        "filters_total": 5,
        "filters": {
            "directionality": {"passed": current["filters"]["directionality"], **current["squeeze"]},
            "adx_strength": {"passed": current["filters"]["adx_weakening"], "value": current["adx"], "previous": current["previous_adx"], "slope": "falling" if current["adx"] is not None and current["previous_adx"] is not None and current["adx"] < current["previous_adx"] else "rising_or_flat", "method": "wilder_adx_14"},
            "ema_value_area": {"passed": current["filters"]["ema55_support"], "ema10": current["ema10"], "ema55": current["ema55"], "distance_ema55_pct": current["distance_ema55_pct"], "proximity_threshold_pct": 2.0},
            "volume_profile": {"passed": current["filters"]["poc_support"], "poc": current["poc"]["price"], "method": current["poc"]["method"], "warning": "Approximate POC from candle typical-price volume; not a true trade-level VPVR."},
            "time": {"passed": time_filter, "status": time_status, "setup_age_bars": consecutive, "price_progress_pct": progress_pct},
        },
        "guardrail": "This filter contract produces an observable candidate only; it never places an order.",
    }


def find_pivots(candles: list[dict], window: int = 3) -> list[dict]:
    pivots = []
    for index in range(window, len(candles) - window):
        current = candles[index]
        neighborhood = candles[index - window:index + window + 1]
        high = float(current["high"])
        low = float(current["low"])
        if high == max(float(item["high"]) for item in neighborhood):
            pivots.append({"timestamp": current["timestamp"], "type": "high", "price": high})
        elif low == min(float(item["low"]) for item in neighborhood):
            pivots.append({"timestamp": current["timestamp"], "type": "low", "price": low})
    return pivots[-12:]


def analyze_spot_candles(symbol: str, timeframe: str, candles: list[dict]) -> dict:
    if len(candles) < 60:
        raise ValueError("At least 60 closed candles are required for spot portfolio analysis")
    ordered = sorted(candles, key=lambda item: int(item["timestamp"]))
    closes = [float(item["close"]) for item in ordered]
    volumes = [float(item.get("volume") or 0) for item in ordered]
    last = closes[-1]
    sma20 = moving_average(closes, 20)
    sma50 = moving_average(closes, 50)
    sma200 = moving_average(closes, 200)
    range_window = ordered[-90:]
    support = min(float(item["low"]) for item in range_window)
    resistance = max(float(item["high"]) for item in range_window)
    range_position = (last - support) / (resistance - support) if resistance > support else 0.5
    recent_volume = mean(volumes[-20:]) or 0
    previous_volume = mean(volumes[-40:-20]) or 0
    volume_ratio = recent_volume / previous_volume if previous_volume else None
    returns = [(closes[index] / closes[index - 1]) - 1 for index in range(1, len(closes)) if closes[index - 1]]
    volatility = standard_deviation(returns[-30:])

    if sma200 is not None and last > sma20 > sma50 > sma200:
        trend = "strong_uptrend"
    elif last > sma20 and sma20 > sma50:
        trend = "uptrend"
    elif sma200 is not None and last < sma20 < sma50 < sma200:
        trend = "strong_downtrend"
    elif last < sma20 and sma20 < sma50:
        trend = "downtrend"
    else:
        trend = "range_or_transition"

    elevated_volume = volume_ratio is not None and volume_ratio >= 1.15
    if range_position <= 0.35 and elevated_volume and last >= sma20:
        wyckoff = "possible_accumulation"
        evidence = "Lower range location, improving close and elevated relative volume."
    elif range_position >= 0.65 and elevated_volume and last <= sma20:
        wyckoff = "possible_distribution"
        evidence = "Upper range location, weakening close and elevated relative volume."
    elif trend in {"uptrend", "strong_uptrend"}:
        wyckoff = "markup_or_reaccumulation"
        evidence = "Trend structure is positive; phase classification still requires manual event labels."
    elif trend in {"downtrend", "strong_downtrend"}:
        wyckoff = "markdown_or_redistribution"
        evidence = "Trend structure is negative; phase classification still requires manual event labels."
    else:
        wyckoff = "trading_range_unclassified"
        evidence = "Price is inside a range without enough evidence to classify accumulation or distribution."

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles_used": len(ordered),
        "latest_timestamp": ordered[-1]["timestamp"],
        "latest_close": last,
        "chartism": {
            "trend": trend,
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "support_90": support,
            "resistance_90": resistance,
            "range_position_pct": range_position * 100,
            "realized_volatility_30_pct": volatility * 100 if volatility is not None else None,
        },
        "wyckoff": {
            "hypothesis": wyckoff,
            "relative_volume_20": volume_ratio,
            "evidence": evidence,
            "status": "heuristic_hypothesis",
        },
        "elliott": {
            "status": "manual_count_required",
            "pivots": find_pivots(ordered),
            "warning": "Pivots are evidence for manual alternatives; ABRAXAS does not assert an automatic Elliott wave count.",
        },
        "trading_latino_5f": trading_latino_five_filters(ordered),
        "guardrails": [
            "No method in this payload executes an order.",
            "Support and resistance are rolling-window observations, not guaranteed levels.",
            "Wyckoff output is a heuristic hypothesis and requires manual event validation.",
        ],
    }
