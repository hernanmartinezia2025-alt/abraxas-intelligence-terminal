from __future__ import annotations

from collections import Counter


def _avg(values: list[float]) -> float:
    clean = [float(value) for value in values if value is not None]
    return round(sum(clean) / len(clean), 6) if clean else 0.0


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return round(max(low, min(high, value)), 2)


def classify_volatility(volatility: float) -> str:
    if volatility >= 2.5:
        return "explosive"
    if volatility >= 1.2:
        return "high"
    if volatility <= 0.35:
        return "compressed"
    return "normal"


def classify_trend(return_5: float, return_20: float, trend_strength: float) -> str:
    if trend_strength >= 0.35 and return_5 > 0 and return_20 > 0:
        return "uptrend"
    if trend_strength <= -0.35 and return_5 < 0 and return_20 < 0:
        return "downtrend"
    if abs(trend_strength) <= 0.12:
        return "flat"
    return "mixed"


def classify_drawdown(drawdown: float) -> str:
    if drawdown <= -12:
        return "deep"
    if drawdown <= -6:
        return "active"
    if drawdown <= -2:
        return "mild"
    return "contained"


def market_bias(return_5: float, return_20: float, trend_strength: float) -> str:
    score = return_5 * 0.35 + return_20 * 0.35 + trend_strength * 0.3
    if score >= 0.45:
        return "bullish"
    if score <= -0.45:
        return "bearish"
    return "neutral"


def confidence_from_persistence(labels: list[str], selected: str, risk_score: float) -> float:
    if not labels:
        return 0
    persistence = labels.count(selected) / len(labels)
    risk_adjustment = min(12, risk_score * 0.08)
    return _clamp(45 + persistence * 43 + risk_adjustment)


def analyze_regime(symbol: str, timeframe: str, features: list[dict]) -> dict:
    if not features:
        raise ValueError("No hay asset_features suficientes para clasificar regimen.")

    ordered = sorted(features, key=lambda row: int(row["timestamp"]))
    latest = ordered[-1]
    window = ordered[-30:]
    labels = [row["regime_label"] for row in window]
    label_counts = Counter(labels)

    return_5 = float(latest["return_5"])
    return_20 = float(latest["return_20"])
    volatility = float(latest["volatility"])
    z_score = float(latest["z_score"])
    drawdown = float(latest["drawdown"])
    trend_strength = float(latest["trend_strength"])
    risk_score = float(latest["risk_score"])
    volume_change = float(latest["volume_change"])

    volatility_state = classify_volatility(volatility)
    trend_state = classify_trend(return_5, return_20, trend_strength)
    drawdown_state = classify_drawdown(drawdown)
    bias = market_bias(return_5, return_20, trend_strength)

    regime_label = latest["regime_label"]
    if risk_score >= 72 or volatility_state == "explosive" or drawdown_state == "deep":
        regime_label = "stress"
    elif abs(z_score) >= 2.2:
        regime_label = "extended"
    elif trend_state == "uptrend":
        regime_label = "momentum_up"
    elif trend_state == "downtrend":
        regime_label = "momentum_down"
    elif volatility_state == "compressed":
        regime_label = "compression"

    reasons = build_reasons(
        regime_label=regime_label,
        bias=bias,
        volatility_state=volatility_state,
        trend_state=trend_state,
        drawdown_state=drawdown_state,
        risk_score=risk_score,
        z_score=z_score,
        volume_change=volume_change,
        label_counts=label_counts,
    )
    confidence = confidence_from_persistence(labels, regime_label, risk_score)

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "timestamp": int(latest["timestamp"]),
        "regime_label": regime_label,
        "confidence": confidence,
        "risk_score": round(risk_score, 2),
        "market_bias": bias,
        "volatility_state": volatility_state,
        "trend_state": trend_state,
        "drawdown_state": drawdown_state,
        "feature_count": len(features),
        "window_count": len(window),
        "label_distribution": dict(label_counts),
        "latest_features": latest,
        "rolling_context": {
            "avg_risk_score": _avg([row["risk_score"] for row in window]),
            "avg_volatility": _avg([row["volatility"] for row in window]),
            "avg_return_5": _avg([row["return_5"] for row in window]),
            "avg_trend_strength": _avg([row["trend_strength"] for row in window]),
        },
        "reasons": reasons,
        "reading": build_regime_reading(symbol=symbol, regime_label=regime_label, bias=bias, risk_score=risk_score, reasons=reasons),
    }


def build_reasons(
    regime_label: str,
    bias: str,
    volatility_state: str,
    trend_state: str,
    drawdown_state: str,
    risk_score: float,
    z_score: float,
    volume_change: float,
    label_counts: Counter,
) -> list[str]:
    reasons = [
        f"Regimen base: {regime_label}.",
        f"Sesgo de mercado: {bias}.",
        f"Volatilidad: {volatility_state}.",
        f"Tendencia: {trend_state}.",
        f"Drawdown: {drawdown_state}.",
    ]
    if risk_score >= 65:
        reasons.append(f"Riesgo elevado por score {risk_score:.2f}.")
    if abs(z_score) >= 2:
        reasons.append(f"Precio extendido: z-score {z_score:.2f}.")
    if volume_change >= 80:
        reasons.append(f"Volumen relativo acelerado: {volume_change:.1f}%.")
    if label_counts:
        dominant, count = label_counts.most_common(1)[0]
        reasons.append(f"Persistencia reciente: {dominant} domina {count} velas de la ventana.")
    return reasons


def build_regime_reading(symbol: str, regime_label: str, bias: str, risk_score: float, reasons: list[str]) -> str:
    if regime_label == "stress":
        base = "mercado bajo presion. Priorizar control de riesgo sobre busqueda de entrada."
    elif regime_label == "extended":
        base = "precio extendido contra su media. Puede seguir, pero aumenta el riesgo de perseguir movimiento."
    elif regime_label == "momentum_up":
        base = "momentum alcista activo. La direccion es constructiva, pero validar volumen y riesgo."
    elif regime_label == "momentum_down":
        base = "momentum bajista activo. Evitar romantizar rebotes sin confirmacion."
    elif regime_label == "compression":
        base = "volatilidad comprimida. El mercado puede estar acumulando energia para ruptura."
    else:
        base = "regimen neutral. Observar estructura antes de forzar narrativa."

    return f"{symbol}: {base} Sesgo {bias}, risk score {risk_score:.2f}. {reasons[0]}"
