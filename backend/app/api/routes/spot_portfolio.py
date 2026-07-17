from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.analytics.spot_analysis import analyze_spot_candles
from backend.app.services.candle_service import get_candles
from backend.app.services.radar_service import get_radar
from backend.app.storage.risk import get_risk_profile
from backend.app.storage.spot_portfolio import execute_spot_transaction, portfolio_snapshot, project_contributions

router = APIRouter(prefix="/api/spot-portfolio", tags=["spot-portfolio"])


class SpotTransactionRequest(BaseModel):
    symbol: str = Field(min_length=3, max_length=30)
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0, le=1_000_000_000)
    notes: str = Field(default="", max_length=500)


def values(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@router.get("")
def spot_portfolio() -> dict:
    try:
        return portfolio_snapshot()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/transactions")
def spot_transaction(payload: SpotTransactionRequest) -> dict:
    try:
        return execute_spot_transaction(values(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projection")
def spot_projection(
    initial_value: float = Query(ge=0, le=1_000_000_000),
    monthly_contribution: float = Query(default=0, ge=0, le=10_000_000),
    years: int = Query(default=4, ge=1, le=40),
    annual_return_pct: float = Query(default=0, ge=-95, le=500),
) -> dict:
    return project_contributions(initial_value, monthly_contribution, years, annual_return_pct)


@router.get("/analysis")
def spot_analysis(
    symbol: str = Query(default="BTCUSDT", min_length=3, max_length=30),
    timeframe: str = Query(default="1d", pattern="^(1d|1w)$"),
    limit: int = Query(default=300, ge=60, le=1000),
) -> dict:
    try:
        payload = get_candles(symbol=symbol.upper(), interval=timeframe, limit=limit)
        result = analyze_spot_candles(
            symbol.upper(),
            timeframe,
            payload["candles"],
            sentiment=get_radar().get("sentiment"),
            risk_profile=get_risk_profile(audit_limit=0),
        )
        result["data_source"] = payload.get("source")
        result["served_from"] = payload.get("served_from")
        return result
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
