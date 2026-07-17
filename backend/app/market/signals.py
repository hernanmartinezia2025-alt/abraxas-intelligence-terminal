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
        "HIGH_EUPHORIA_RISK": f"{symbol}: impulso alcista con euforia. Accion: no perseguir; esperar retroceso y confirmar volumen.",
        "HIGH_FEAR_RISK": f"{symbol}: presion vendedora con miedo extremo. Accion: vigilar acumulacion; no comprar sin estabilizacion.",
        "HIGH_VOLATILITY": f"{symbol}: rango de movimiento elevado. Accion: reducir tamano y exigir confirmacion antes de operar.",
        "NORMAL": f"{symbol}: sin extremo estadistico en el snapshot. Accion: observar rango, liquidez y confirmacion.",
    }
    return readings.get(risk_level, readings["NORMAL"])
