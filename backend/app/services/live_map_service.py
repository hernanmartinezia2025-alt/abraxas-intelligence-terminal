from __future__ import annotations

from datetime import datetime, timezone

from backend.app.live_map.clients import fetch_gdelt_news, fetch_gdacs_alerts, fetch_usgs_earthquakes, timed_fetch
from backend.app.storage.live_map import (
    latest_live_fetch_at,
    list_live_events,
    list_market_relevant_events,
    list_source_health,
    save_live_events,
    save_source_health,
)
from backend.app.storage.sqlite import initialize_database

CACHE_TTL_MINUTES = 12


def should_refresh_cache() -> bool:
    fetched_at = latest_live_fetch_at()
    if not fetched_at:
        return True
    try:
        fetched = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return True
    age_minutes = (datetime.now(timezone.utc) - fetched).total_seconds() / 60
    return age_minutes >= CACHE_TTL_MINUTES


def refresh_live_map() -> dict:
    initialize_database()
    fetch_jobs = [
        ("GDELT", lambda: fetch_gdelt_news(limit=55), 30),
        ("USGS", lambda: fetch_usgs_earthquakes(limit=80), 20),
        ("GDACS", lambda: fetch_gdacs_alerts(limit=80), 30),
    ]
    all_events = []
    health_records = []

    for source, fetcher, max_stale_minutes in fetch_jobs:
        events, health = timed_fetch(source, fetcher, max_stale_minutes)
        all_events.extend(events)
        health_records.append(health)

    saved = save_live_events(all_events)
    save_source_health(health_records)
    return {"saved": saved, "source_health": list_source_health()}


def get_live_events(
    *,
    event_types: list[str] | None = None,
    limit: int = 250,
    refresh: bool = False,
) -> dict:
    initialize_database()
    if refresh or should_refresh_cache():
        refresh_live_map()
    events = list_live_events(limit=limit, event_types=event_types)
    return {
        "events": events,
        "count": len(events),
        "source_health": list_source_health(),
    }


def get_live_news(limit: int = 160, refresh: bool = False) -> dict:
    return get_live_events(event_types=["news"], limit=limit, refresh=refresh)


def get_live_alerts(limit: int = 160, refresh: bool = False) -> dict:
    initialize_database()
    if refresh or should_refresh_cache():
        refresh_live_map()

    direct_alerts = list_live_events(limit=limit, event_types=["earthquake", "disaster", "security"])
    market_alerts = list_market_relevant_events(limit=limit)
    by_key = {}
    for event in [*direct_alerts, *market_alerts]:
        by_key[f"{event['source']}:{event['id']}"] = event

    events = sorted(
        by_key.values(),
        key=lambda event: (
            {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(event.get("severity"), 0),
            event.get("published_at", ""),
        ),
        reverse=True,
    )[:limit]
    return {"events": events, "count": len(events), "source_health": list_source_health()}


def get_live_map_health() -> dict:
    initialize_database()
    return {
        "ok": True,
        "cache_stale": should_refresh_cache(),
        "sources": list_source_health(),
    }

