from __future__ import annotations

from math import sqrt


def _point(candle: dict, value: float) -> dict:
    return {"timestamp": int(candle["timestamp"]), "value": float(value)}


def simple_moving_average(candles: list[dict], period: int) -> list[dict]:
    if period < 2:
        raise ValueError("SMA period must be at least 2.")
    points: list[dict] = []
    rolling = 0.0
    for index, candle in enumerate(candles):
        rolling += float(candle["close"])
        if index >= period:
            rolling -= float(candles[index - period]["close"])
        if index + 1 >= period:
            points.append(_point(candle, rolling / period))
    return points


def exponential_moving_average(candles: list[dict], period: int) -> list[dict]:
    if period < 2:
        raise ValueError("EMA period must be at least 2.")
    if len(candles) < period:
        return []
    alpha = 2 / (period + 1)
    seed = sum(float(item["close"]) for item in candles[:period]) / period
    points = [_point(candles[period - 1], seed)]
    current = seed
    for candle in candles[period:]:
        current = float(candle["close"]) * alpha + current * (1 - alpha)
        points.append(_point(candle, current))
    return points


def bollinger_bands(candles: list[dict], period: int, deviation: float) -> dict[str, list[dict]]:
    if period < 2:
        raise ValueError("Bollinger period must be at least 2.")
    if deviation <= 0:
        raise ValueError("Bollinger deviation must be positive.")
    middle: list[dict] = []
    upper: list[dict] = []
    lower: list[dict] = []
    for index in range(period - 1, len(candles)):
        window = [float(item["close"]) for item in candles[index + 1 - period:index + 1]]
        average = sum(window) / period
        standard_deviation = sqrt(sum((value - average) ** 2 for value in window) / period)
        candle = candles[index]
        middle.append(_point(candle, average))
        upper.append(_point(candle, average + standard_deviation * deviation))
        lower.append(_point(candle, average - standard_deviation * deviation))
    return {"middle": middle, "upper": upper, "lower": lower}


def compute_indicator(candles: list[dict], config: dict) -> dict:
    kind = config["kind"]
    period = int(config["period"])
    if kind == "sma":
        series = {"value": simple_moving_average(candles, period)}
    elif kind == "ema":
        series = {"value": exponential_moving_average(candles, period)}
    elif kind == "bollinger":
        series = bollinger_bands(candles, period, float(config["deviation"]))
    else:
        raise ValueError(f"Unsupported chart indicator kind: {kind}.")
    return {"config": config, "series": series}
