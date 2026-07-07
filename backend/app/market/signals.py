from __future__ import annotations


def classify_risk(fear_greed_value: int, change_24h: float) -> str:
    if fear_greed_value >= 75 and change_24h > 3:
        return "HIGH_EUPHORIA_RISK"
    if fear_greed_value <= 25 and change_24h < -3:
        return "HIGH_FEAR_RISK"
    if abs(change_24h) >= 5:
        return "HIGH_VOLATILITY"
    return "NORMAL"


def build_reading(symbol: str, risk_level: str) -> str:
    readings = {
        "HIGH_EUPHORIA_RISK": f"{symbol}: suba con codicia alta. Riesgo de entrada tardia del retail. No perseguir vela.",
        "HIGH_FEAR_RISK": f"{symbol}: caida con miedo alto. Puede haber panico real o zona de oportunidad. Mirar volumen.",
        "HIGH_VOLATILITY": f"{symbol}: movimiento fuerte. El mercado esta activo, pero no necesariamente claro.",
        "NORMAL": f"{symbol}: mercado sin senal extrema. Observar, no inventar epica.",
    }
    return readings.get(risk_level, readings["NORMAL"])