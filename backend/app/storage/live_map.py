from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

from backend.app.storage.sqlite import connect, initialize_database

SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_list(value: list[str] | None) -> str:
    return json.dumps(value or [], ensure_ascii=True)


def deserialize_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        payload = json.loads(value)
        return payload if isinstance(payload, list) else []
    except json.JSONDecodeError:
        return []


def save_live_events(events: Iterable[dict]) -> int:
    initialize_database()
    fetched_at = utc_now_iso()
    rows = []
    for event in events:
        rows.append(
            {
                **event,
                "source": event.get("source") or "unknown",
                "related_assets": serialize_list(event.get("related_assets")),
                "vector_tags": serialize_list(event.get("vector_tags")),
                "raw_payload": json.dumps(event.get("raw_payload") or {}, ensure_ascii=True),
                "fetched_at": fetched_at,
            }
        )

    if not rows:
        return 0

    with connect() as connection:
        connection.executemany(
            """
            INSERT INTO live_events (
                id, source, type, title, summary, lat, lon, country, url, severity,
                published_at, freshness_minutes, related_assets, vector_tags,
                raw_url, fetched_at, raw_payload
            ) VALUES (
                :id, :source, :type, :title, :summary, :lat, :lon, :country, :url, :severity,
                :published_at, :freshness_minutes, :related_assets, :vector_tags,
                :raw_url, :fetched_at, :raw_payload
            )
            ON CONFLICT(source, id) DO UPDATE SET
                type = excluded.type,
                title = excluded.title,
                summary = excluded.summary,
                lat = excluded.lat,
                lon = excluded.lon,
                country = excluded.country,
                url = excluded.url,
                severity = excluded.severity,
                published_at = excluded.published_at,
                freshness_minutes = excluded.freshness_minutes,
                related_assets = excluded.related_assets,
                vector_tags = excluded.vector_tags,
                raw_url = excluded.raw_url,
                fetched_at = excluded.fetched_at,
                raw_payload = excluded.raw_payload
            """,
            rows,
        )
    return len(rows)


def save_source_health(records: Iterable[dict]) -> None:
    initialize_database()
    checked_at = utc_now_iso()
    rows = []
    for record in records:
        rows.append(
            {
                "source": record["source"],
                "ok": 1 if record.get("ok") else 0,
                "last_success_at": record.get("last_success_at"),
                "latency_ms": int(record.get("latency_ms") or 0),
                "event_count": int(record.get("event_count") or 0),
                "error": record.get("error") or "",
                "max_stale_minutes": int(record.get("max_stale_minutes") or 30),
                "checked_at": checked_at,
            }
        )

    if not rows:
        return

    with connect() as connection:
        connection.executemany(
            """
            INSERT INTO live_source_health (
                source, ok, last_success_at, latency_ms, event_count,
                error, max_stale_minutes, checked_at
            ) VALUES (
                :source, :ok, :last_success_at, :latency_ms, :event_count,
                :error, :max_stale_minutes, :checked_at
            )
            ON CONFLICT(source) DO UPDATE SET
                ok = excluded.ok,
                last_success_at = COALESCE(excluded.last_success_at, live_source_health.last_success_at),
                latency_ms = excluded.latency_ms,
                event_count = excluded.event_count,
                error = excluded.error,
                max_stale_minutes = excluded.max_stale_minutes,
                checked_at = excluded.checked_at
            """,
            rows,
        )


def list_live_events(limit: int = 250, event_types: list[str] | None = None) -> list[dict]:
    initialize_database()
    params: list[object] = []
    where = "WHERE lat IS NOT NULL AND lon IS NOT NULL"
    if event_types:
        placeholders = ",".join("?" for _ in event_types)
        where += f" AND type IN ({placeholders})"
        params.extend(event_types)
    params.append(limit)

    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM live_events
            {where}
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 4
                    WHEN 'high' THEN 3
                    WHEN 'medium' THEN 2
                    ELSE 1
                END DESC,
                published_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [normalize_row(dict(row)) for row in rows]


def list_market_relevant_events(limit: int = 120) -> list[dict]:
    events = list_live_events(limit=400)
    relevant = [event for event in events if event.get("related_assets")]
    return sorted(relevant, key=lambda event: (SEVERITY_ORDER.get(event["severity"], 0), event["published_at"]), reverse=True)[
        :limit
    ]


def list_source_health() -> list[dict]:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT source, ok, last_success_at, latency_ms, event_count,
                   error, max_stale_minutes, checked_at
            FROM live_source_health
            ORDER BY source
            """
        ).fetchall()
    return [{**dict(row), "ok": bool(row["ok"])} for row in rows]


def latest_live_fetch_at() -> str | None:
    initialize_database()
    with connect() as connection:
        row = connection.execute("SELECT MAX(fetched_at) AS fetched_at FROM live_events").fetchone()
    return row["fetched_at"] if row and row["fetched_at"] else None


def normalize_row(row: dict) -> dict:
    row.pop("row_id", None)
    row["related_assets"] = deserialize_list(row.get("related_assets"))
    row["vector_tags"] = deserialize_list(row.get("vector_tags"))
    row["freshness_minutes"] = int(row.get("freshness_minutes") or 0)
    return row

