from __future__ import annotations

from datetime import datetime, timezone

from backend.app.core.config import DEFAULT_SYMBOLS
from backend.app.market.binance import fetch_24h_tickers
from backend.app.market.sentiment import fetch_fear_greed
from backend.app.market.sentiment_analysis import build_sentiment_analysis
from backend.app.market.signals import build_reading, classify_risk
from backend.app.storage.sqlite import connect, initialize_database


def update_market(symbols: list[str] | None = None) -> list[dict]:
    initialize_database()
    selected = symbols or DEFAULT_SYMBOLS
    sentiment = fetch_fear_greed()
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = []

    for ticker in fetch_24h_tickers(selected):
        risk_level = classify_risk(sentiment["value"], ticker["change_24h"])
        row = {
            "timestamp": timestamp,
            "symbol": ticker["symbol"],
            "price": ticker["price"],
            "change_24h": ticker["change_24h"],
            "volume_24h": ticker["volume_24h"],
            "fear_greed_value": sentiment["value"],
            "fear_greed_label": sentiment["label"],
            "risk_level": risk_level,
            "abraxas_reading": build_reading(ticker["symbol"], risk_level),
        }
        rows.append(row)

    with connect() as connection:
        connection.executemany(
            """
            INSERT INTO market_snapshots (
                timestamp, symbol, price, change_24h, volume_24h,
                fear_greed_value, fear_greed_label, risk_level, abraxas_reading
            ) VALUES (
                :timestamp, :symbol, :price, :change_24h, :volume_24h,
                :fear_greed_value, :fear_greed_label, :risk_level, :abraxas_reading
            )
            """,
            rows,
        )
    return rows


def get_latest(limit: int = 160) -> list[dict]:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM market_snapshots
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_radar() -> dict:
    rows = get_latest()
    return {
        "latest_snapshots": rows,
        "symbols": sorted({row["symbol"] for row in rows}),
        "count": len(rows),
        "sentiment": build_sentiment_analysis(rows),
    }
