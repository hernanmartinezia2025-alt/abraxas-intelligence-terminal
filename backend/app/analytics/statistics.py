from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _round(value: float | int | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    if pd.isna(value) or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def candles_to_frame(candles: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(candles)
    if frame.empty:
        raise ValueError("No hay candles suficientes para calcular estadistica.")

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    numeric_columns = ["open", "high", "low", "close", "volume", "quote_volume"]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["close"]).sort_values("timestamp").reset_index(drop=True)
    frame["return"] = frame["close"].pct_change()
    frame["return_pct"] = frame["return"] * 100
    frame["log_return"] = np.log(frame["close"] / frame["close"].shift(1))
    frame["rolling_mean"] = frame["close"].rolling(20).mean()
    frame["rolling_std"] = frame["close"].rolling(20).std()
    frame["rolling_z_score"] = (frame["close"] - frame["rolling_mean"]) / frame["rolling_std"]
    frame["equity_curve"] = (1 + frame["return"].fillna(0)).cumprod()
    frame["running_peak"] = frame["equity_curve"].cummax()
    frame["drawdown_pct"] = ((frame["equity_curve"] / frame["running_peak"]) - 1) * 100
    return frame


def build_distribution(returns_pct: pd.Series, bins: int = 18) -> dict:
    clean = returns_pct.dropna()
    if len(clean) < 5:
        return {"bins": [], "sample_count": int(len(clean))}

    counts, edges = np.histogram(clean.to_numpy(), bins=bins)
    rows = []
    for index, count in enumerate(counts):
        rows.append(
            {
                "from": _round(edges[index], 4),
                "to": _round(edges[index + 1], 4),
                "count": int(count),
            }
        )
    return {"bins": rows, "sample_count": int(len(clean))}


def gaussian_curve(returns_pct: pd.Series, points: int = 41) -> list[dict]:
    clean = returns_pct.dropna()
    if len(clean) < 5:
        return []

    mean = float(clean.mean())
    std = float(clean.std())
    if std == 0 or not math.isfinite(std):
        return []

    xs = np.linspace(mean - 3 * std, mean + 3 * std, points)
    density = (1 / (std * math.sqrt(2 * math.pi))) * np.exp(-0.5 * ((xs - mean) / std) ** 2)
    return [{"x": _round(x, 4), "y": _round(y, 8)} for x, y in zip(xs, density)]


def summarize_statistics(symbol: str, interval: str, candles: list[dict]) -> dict:
    frame = candles_to_frame(candles)
    returns = frame["return_pct"].dropna()
    latest = frame.iloc[-1]
    current_price = float(latest["close"])
    first_price = float(frame.iloc[0]["close"])
    total_move_pct = ((current_price / first_price) - 1) * 100 if first_price else 0
    latest_return = float(returns.iloc[-1]) if not returns.empty else 0
    volatility = float(returns.std()) if len(returns) > 1 else 0
    mean_return = float(returns.mean()) if not returns.empty else 0
    z_score = float(latest["rolling_z_score"]) if pd.notna(latest["rolling_z_score"]) else 0

    abs_returns = returns.abs()
    latest_abs = abs(latest_return)
    percentile = float((abs_returns <= latest_abs).mean() * 100) if len(abs_returns) else 0
    var_95 = float(returns.quantile(0.05)) if len(returns) else 0
    ci_low = mean_return - 1.96 * volatility
    ci_high = mean_return + 1.96 * volatility

    return {
        "symbol": symbol,
        "interval": interval,
        "sample_count": int(len(frame)),
        "current_price": _round(current_price, 8),
        "first_price": _round(first_price, 8),
        "total_move_pct": _round(total_move_pct, 4),
        "latest_return_pct": _round(latest_return, 4),
        "mean_return_pct": _round(mean_return, 4),
        "volatility_pct": _round(volatility, 4),
        "z_score": _round(z_score, 4),
        "latest_move_percentile": _round(percentile, 2),
        "max_drawdown_pct": _round(float(frame["drawdown_pct"].min()), 4),
        "var_95_pct": _round(var_95, 4),
        "confidence_interval_95_pct": [_round(ci_low, 4), _round(ci_high, 4)],
        "distribution": build_distribution(returns),
        "gaussian_curve": gaussian_curve(returns),
        "reading": explain_statistics(
            symbol=symbol,
            z_score=z_score,
            percentile=percentile,
            volatility=volatility,
            var_95=var_95,
            total_move_pct=total_move_pct,
        ),
    }


def run_monte_carlo(
    symbol: str,
    interval: str,
    candles: list[dict],
    horizon_steps: int = 48,
    paths: int = 700,
) -> dict:
    frame = candles_to_frame(candles)
    returns = frame["log_return"].dropna()
    if len(returns) < 10:
        raise ValueError("No hay retornos suficientes para Monte Carlo.")

    current_price = float(frame.iloc[-1]["close"])
    mean = float(returns.mean())
    std = float(returns.std())
    rng = np.random.default_rng(42)
    shocks = rng.normal(loc=mean, scale=std, size=(paths, horizon_steps))
    simulated = current_price * np.exp(np.cumsum(shocks, axis=1))
    final_prices = simulated[:, -1]
    final_returns = ((final_prices / current_price) - 1) * 100

    percentiles = {
        "p05": _round(np.percentile(final_prices, 5), 8),
        "p25": _round(np.percentile(final_prices, 25), 8),
        "p50": _round(np.percentile(final_prices, 50), 8),
        "p75": _round(np.percentile(final_prices, 75), 8),
        "p95": _round(np.percentile(final_prices, 95), 8),
    }
    probability_up = float((final_prices > current_price).mean() * 100)
    probability_down = 100 - probability_up

    sample_paths = []
    for path_index in range(min(18, paths)):
        path = simulated[path_index]
        sample_paths.append(
            {
                "id": path_index + 1,
                "points": [_round(value, 8) for value in path[:: max(1, horizon_steps // 24)]],
            }
        )

    return {
        "symbol": symbol,
        "interval": interval,
        "current_price": _round(current_price, 8),
        "horizon_steps": horizon_steps,
        "paths": paths,
        "percentiles": percentiles,
        "probability_up_pct": _round(probability_up, 2),
        "probability_down_pct": _round(probability_down, 2),
        "expected_return_pct": _round(float(final_returns.mean()), 4),
        "stress_return_pct": _round(float(np.percentile(final_returns, 5)), 4),
        "sample_paths": sample_paths,
        "reading": explain_monte_carlo(symbol, probability_up, percentiles, current_price),
        "disclaimer": "Monte Carlo modela escenarios probables con retornos historicos. No predice precio ni recomienda inversion.",
    }


def explain_statistics(
    symbol: str,
    z_score: float,
    percentile: float,
    volatility: float,
    var_95: float,
    total_move_pct: float,
) -> str:
    direction = "sobre" if z_score >= 0 else "debajo de"
    intensity = "normal"
    if abs(z_score) >= 2:
        intensity = "extremo"
    elif abs(z_score) >= 1:
        intensity = "elevado"

    return (
        f"{symbol}: el precio esta {abs(z_score):.2f} desviaciones {direction} su media corta. "
        f"El movimiento cae en percentil {percentile:.0f} de tamano reciente y la volatilidad media por vela es {volatility:.2f}%. "
        f"Lectura: regimen {intensity}; VaR 95 aproximado por vela {var_95:.2f}% y movimiento total de muestra {total_move_pct:.2f}%."
    )


def explain_monte_carlo(symbol: str, probability_up: float, percentiles: dict, current_price: float) -> str:
    median = percentiles["p50"]
    p05 = percentiles["p05"]
    p95 = percentiles["p95"]
    bias = "alcista" if probability_up >= 55 else "bajista" if probability_up <= 45 else "mixto"
    return (
        f"{symbol}: Monte Carlo marca sesgo {bias} en esta ventana, con {probability_up:.1f}% de rutas cerrando arriba del precio actual. "
        f"Rango central simulado: mediana {median}, cola baja {p05}, cola alta {p95}. Esto es mapa de escenarios, no certeza."
    )
