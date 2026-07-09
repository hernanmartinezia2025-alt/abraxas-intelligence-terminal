from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.order_book_service import get_order_book

router = APIRouter(prefix="/api", tags=["order-book"])


@router.get("/order-book")
def order_book(
    symbol: str = Query(default="BTCUSDT"),
    limit: int = Query(default=20, ge=5, le=100),
) -> dict:
    try:
        return get_order_book(symbol=symbol, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
