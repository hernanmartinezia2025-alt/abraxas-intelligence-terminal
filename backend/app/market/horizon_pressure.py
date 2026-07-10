from __future__ import annotations

from typing import Any

from backend.app.storage.sqlite import connect, initialize_database


def build_horizon_pressure(symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")) -> list[dict[str, Any]]:
    initialize_database()
    result = []
    with connect() as connection:
        for timeframe, label in (("1h", "1 hora"), ("4h", "4 horas"), ("1d", "Diario")):
            returns = []
            for symbol in symbols:
                rows = connection.execute(
                    "SELECT close FROM market_candles WHERE symbol = ? AND timeframe = ? ORDER BY open_time DESC LIMIT 2",
                    (symbol, timeframe),
                ).fetchall()
                if len(rows) == 2 and float(rows[1]["close"] or 0):
                    returns.append((float(rows[0]["close"]) / float(rows[1]["close"]) - 1) * 100)
            if not returns:
                result.append({"key": timeframe, "label": label, "status": "unavailable", "reason": "Candles insuficientes."})
                continue
            value = round(sum(returns) / len(returns), 3)
            regime = "FOMO pressure" if value >= 1.5 else "FUD pressure" if value <= -1.5 else "neutral pressure"
            result.append({
                "key": timeframe,
                "label": label,
                "status": "available",
                "value": value,
                "regime": regime,
                "reason": f"Retorno medio de {len(returns)} activos desde Binance candles.",
            })
    return result
