from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.services.radar_service import get_radar, update_market

router = APIRouter(prefix="/api/radar", tags=["radar"])


@router.get("")
def radar() -> dict:
    return get_radar()


@router.post("/update")
def radar_update() -> dict:
    try:
        rows = update_market()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"saved": len(rows), "rows": rows}