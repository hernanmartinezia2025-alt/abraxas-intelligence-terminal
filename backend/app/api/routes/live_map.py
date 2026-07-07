from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.live_map_service import get_live_alerts, get_live_events, get_live_map_health, get_live_news

router = APIRouter(prefix="/api/live-map", tags=["live-map"])


@router.get("/events")
def live_map_events(
    refresh: bool = Query(default=False),
    limit: int = Query(default=250, ge=20, le=500),
    types: str | None = Query(default=None, description="Comma-separated event types"),
) -> dict:
    event_types = [part.strip() for part in types.split(",") if part.strip()] if types else None
    try:
        return get_live_events(event_types=event_types, limit=limit, refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/news")
def live_map_news(
    refresh: bool = Query(default=False),
    limit: int = Query(default=160, ge=10, le=300),
) -> dict:
    try:
        return get_live_news(limit=limit, refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/alerts")
def live_map_alerts(
    refresh: bool = Query(default=False),
    limit: int = Query(default=160, ge=10, le=300),
) -> dict:
    try:
        return get_live_alerts(limit=limit, refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/health")
def live_map_health() -> dict:
    return get_live_map_health()

