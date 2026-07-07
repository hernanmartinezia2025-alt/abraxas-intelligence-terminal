from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _safe_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if pd.isna(numeric) or not math.isfinite(numeric):
        return None
    return round(numeric, 6)


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def classify_regime(return_5: float, trend_strength: float, volatility: float, drawdown: float, z_score: float) -> str:
    if drawdown <= -8 or volatility >= 2.5:
        return "stress"
    if abs(z_score) >= 2.2:
        return "extended"
    if trend_strength >= 0.35 and return_5 > 0:
        return "momentum_up"
    if trend_strength <= -0.35 and return_5 < 0:
        return "momentum_down"
    if volatility <= 0.35 and abs(return_5) <= 1:
        return "compression"
    return "neutral"


def calculate_risk_score(volatility: float, z_score: float, drawdown: float, volume_change: float) -> float:
    vol_component = min(32, abs(volatility) * 14)
    z_component = min(28, abs(z_score) * 12)
    drawdown_component = min(24, abs(min(drawdown, 0)) * 2.1)
    volume_component = min(16, max(volume_change, 0) * 0.08)
    return round(_clamp(vol_component + z_component + drawdown_component + volume_component), 2)


def build_asset_features(symbol: str, timeframe: str, candles: list[dict]) -> list[dict]:
    frame = pd.DataFrame(candles)
    if frame.empty or len(frame) < 30:
        return []

    frame = frame.sort_values("timestamp").reset_index(drop=True)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["close", "volume"])

    frame["return_1"] = frame["close"].pct_change(1) * 100
    frame["return_5"] = frame["close"].pct_change(5) * 100
    frame["return_20"] = frame["close"].pct_change(20) * 100
    frame["volatility"] = frame["return_1"].rolling(20).std()
    rolling_mean = frame["close"].rolling(20).mean()
    rolling_std = frame["close"].rolling(20).std()
    frame["z_score"] = (frame["close"] - rolling_mean) / rolling_std.replace(0, np.nan)
    equity_curve = frame["close"] / frame["close"].iloc[0]
    frame["drawdown"] = ((equity_curve / equity_curve.cummax()) - 1) * 100
    ema_fast = frame["close"].ewm(span=12, adjust=False).mean()
    ema_slow = frame["close"].ewm(span=26, adjust=False).mean()
    frame["trend_strength"] = ((ema_fast - ema_slow) / frame["close"]) * 100
    volume_base = frame["volume"].rolling(20).mean()
    frame["volume_change"] = ((frame["volume"] / volume_base.replace(0, np.nan)) - 1) * 100

    rows = []
    for row in frame.to_dict("records"):
        required = [
            row.get("return_1"),
            row.get("return_5"),
            row.get("return_20"),
            row.get("volatility"),
            row.get("z_score"),
            row.get("drawdown"),
            row.get("trend_strength"),
            row.get("volume_change"),
        ]
        if any(_safe_float(value) is None for value in required):
            continue

        return_5 = float(row["return_5"])
        volatility = float(row["volatility"])
        z_score = float(row["z_score"])
        drawdown = float(row["drawdown"])
        trend_strength = float(row["trend_strength"])
        volume_change = float(row["volume_change"])
        rows.append(
            {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "timestamp": int(row["timestamp"]),
                "return_1": _safe_float(row["return_1"]),
                "return_5": _safe_float(return_5),
                "return_20": _safe_float(row["return_20"]),
                "volatility": _safe_float(volatility),
                "z_score": _safe_float(z_score),
                "drawdown": _safe_float(drawdown),
                "trend_strength": _safe_float(trend_strength),
                "volume_change": _safe_float(volume_change),
                "risk_score": calculate_risk_score(
                    volatility=volatility,
                    z_score=z_score,
                    drawdown=drawdown,
                    volume_change=volume_change,
                ),
                "regime_label": classify_regime(
                    return_5=return_5,
                    trend_strength=trend_strength,
                    volatility=volatility,
                    drawdown=drawdown,
                    z_score=z_score,
                ),
            }
        )

    return rows
