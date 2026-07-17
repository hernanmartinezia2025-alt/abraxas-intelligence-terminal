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
        "guardrails": [
            "No method in this payload executes an order.",
            "Support and resistance are rolling-window observations, not guaranteed levels.",
            "Wyckoff output is a heuristic hypothesis and requires manual event validation.",
        ],
    }
