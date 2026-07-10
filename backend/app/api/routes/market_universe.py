from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.macro_market_service import get_macro_universe

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/universe")
def market_universe(category: str = Query(default="indices"), refresh: bool = Query(default=False)) -> dict:
    try:
        return get_macro_universe(category=category, refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
