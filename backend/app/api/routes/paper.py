from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.storage.paper import account_snapshot, place_market_order, reconcile_paper_runtime, reset_account

router = APIRouter(prefix="/api/paper", tags=["paper-trading"])


class PaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=30)
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0, le=1_000_000_000)
    bot_id: int | None = Field(default=None, ge=1)


class PaperResetRequest(BaseModel):
    initial_balance: float = Field(default=10_000, gt=0, le=1_000_000_000)
    reason: str = Field(min_length=3, max_length=500)


def values(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@router.get("")
def paper_account() -> dict:
    return account_snapshot()


@router.post("/orders")
def paper_order(payload: PaperOrderRequest) -> dict:
    try:
        return place_market_order(values(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reset")
def paper_reset(payload: PaperResetRequest) -> dict:
    data = values(payload)
    return reset_account(data["initial_balance"], data["reason"])


@router.post("/reconcile")
def paper_reconcile() -> dict:
    return reconcile_paper_runtime()
