from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.liquidity_sweep_service import evaluate_liquidity_sweep, history, readiness

router = APIRouter(prefix="/api/sl-hunter", tags=["sl-hunter"])


class SweepEvaluationRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", min_length=3, max_length=24)
    timeframe: str = "1m"
    limit: int = Field(default=200, ge=60, le=1000)
    account_equity: float = Field(default=10_000, gt=0, le=1_000_000_000)
    risk_pct: float = Field(default=0.5, gt=0, le=2)


def _payload(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@router.get("/readiness")
def sl_hunter_readiness() -> dict:
    return readiness()


@router.post("/evaluate")
def sl_hunter_evaluate(payload: SweepEvaluationRequest) -> dict:
    try:
        return evaluate_liquidity_sweep(**_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/evaluations")
def sl_hunter_history(
    limit: int = Query(default=20, ge=1, le=200),
    symbol: str = Query(default="", max_length=24),
) -> dict:
    return history(limit=limit, symbol=symbol)
