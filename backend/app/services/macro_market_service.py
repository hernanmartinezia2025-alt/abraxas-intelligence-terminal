from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import requests

from backend.app.core.config import REQUEST_TIMEOUT
from backend.app.storage.sqlite import connect, initialize_database

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
SERIES = {
    "SP500": {"symbol": "SPX", "name": "S&P 500", "category": "indices", "unit": "index"},
    "NASDAQCOM": {"symbol": "NASDAQ", "name": "Nasdaq Composite", "category": "indices", "unit": "index"},
    "DJIA": {"symbol": "DJIA", "name": "Dow Jones", "category": "indices", "unit": "index"},
    "DCOILWTICO": {"symbol": "WTI", "name": "WTI Crude Oil", "category": "commodities", "unit": "USD/barrel"},
    "DTWEXBGS": {"symbol": "USD-BROAD", "name": "Broad U.S. Dollar", "category": "fx", "unit": "index"},
    "DGS10": {"symbol": "US10Y", "name": "U.S. Treasury 10Y", "category": "rates", "unit": "percent"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def refresh_macro_observations(limit: int = 180) -> int:
    initialize_database()
    fetched_at = _now()
    records = []
    for series_id, metadata in SERIES.items():
        response = requests.get(FRED_CSV_URL, params={"id": series_id}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(response.text)))[-limit:]
        for row in rows:
            raw_value = row.get(series_id)
            if not raw_value or raw_value == ".":
                continue
            records.append({
                "series_id": series_id,
                **metadata,
                "observation_date": row["observation_date"],
                "value": float(raw_value),
                "source": "FRED",
                "fetched_at": fetched_at,
            })
    with connect() as connection:
        connection.executemany(
            """
            INSERT INTO macro_observations (
                series_id, symbol, name, category, observation_date, value, unit, source, fetched_at
            ) VALUES (
                :series_id, :symbol, :name, :category, :observation_date, :value, :unit, :source, :fetched_at
            )
            ON CONFLICT(series_id, observation_date) DO UPDATE SET
                value = excluded.value, fetched_at = excluded.fetched_at
            """,
            records,
        )
    return len(records)


def get_macro_universe(category: str, refresh: bool = False) -> dict:
    initialize_database()
    allowed = {metadata["category"] for metadata in SERIES.values()}
    if category not in allowed:
        return {"category": category, "source": "FRED", "items": [], "status": "unsupported"}
    with connect() as connection:
        existing = connection.execute("SELECT COUNT(*) AS count FROM macro_observations WHERE category = ?", (category,)).fetchone()["count"]
    refreshed = 0
    if refresh or not existing:
        refreshed = refresh_macro_observations()
    items = []
    for series_id, metadata in SERIES.items():
        if metadata["category"] != category:
            continue
        with connect() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT observation_date, value FROM macro_observations WHERE series_id = ? ORDER BY observation_date DESC LIMIT 60",
                (series_id,),
            ).fetchall()]
        rows.reverse()
        latest = rows[-1]["value"] if rows else None
        previous = rows[-2]["value"] if len(rows) > 1 else None
        change_pct = ((latest / previous) - 1) * 100 if latest is not None and previous else None
        items.append({"series_id": series_id, **metadata, "latest": latest, "change_pct": change_pct, "observations": rows})
    return {"category": category, "source": "FRED", "status": "ready", "refreshed_rows": refreshed, "items": items}


def get_macro_overview(refresh: bool = False) -> dict:
    initialize_database()
    with connect() as connection:
        existing = connection.execute("SELECT COUNT(*) AS count FROM macro_observations").fetchone()["count"]
    refreshed = refresh_macro_observations() if refresh or not existing else 0
    items = []
    with connect() as connection:
        for series_id, metadata in SERIES.items():
            rows = connection.execute(
                """SELECT observation_date, value FROM macro_observations
                WHERE series_id = ? ORDER BY observation_date DESC LIMIT 2""",
                (series_id,),
            ).fetchall()
            latest = float(rows[0]["value"]) if rows else None
            previous = float(rows[1]["value"]) if len(rows) > 1 else None
            change_pct = ((latest / previous) - 1) * 100 if latest is not None and previous else None
            items.append({"series_id": series_id, **metadata, "latest": latest, "change_pct": change_pct, "as_of": rows[0]["observation_date"] if rows else None})

    changes = {item["series_id"]: item["change_pct"] for item in items}
    score_inputs = []
    for series_id, positive_is_risk_on in [("SP500", True), ("NASDAQCOM", True), ("DTWEXBGS", False), ("DGS10", False)]:
        change = changes.get(series_id)
        if change is not None:
            score_inputs.append((1 if change > 0 else -1) * (1 if positive_is_risk_on else -1))
    score = sum(score_inputs)
    regime = "mixed" if len(score_inputs) < 3 else "risk_on" if score >= 2 else "risk_off" if score <= -2 else "mixed"
    guidance = {
        "risk_on": "Activos de riesgo con apoyo macro relativo; exigir confirmacion del activo antes de entrar.",
        "risk_off": "Contexto defensivo; reducir agresividad y priorizar preservacion de capital.",
        "mixed": "Señales macro divididas; evitar inferir direccion sin confirmacion de precio y volumen.",
    }[regime]
    return {
        "source": "FRED",
        "status": "ready",
        "refreshed_rows": refreshed,
        "regime": regime,
        "score": score,
        "guidance": guidance,
        "items": items,
        "missing_sources": [{"asset": "GOLD", "status": "planned", "reason": "Spot gold source pending approval"}],
    }
