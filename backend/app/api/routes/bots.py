from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.bot_service import (
    create_saved_bot,
    create_saved_bot_version,
    get_saved_bot_backtest,
    get_saved_bot,
    list_saved_bot_backtests,
    run_saved_bot_backtest,
    list_saved_bots,
)

router = APIRouter(prefix="/api/bots", tags=["bots"])


class BotCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    base_symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    risk_profile: str = "balanced"
    notes: str = "Version inicial."
    strategy: dict | None = None


class BotVersionRequest(BaseModel):
    strategy: dict
    notes: str = ""


class BacktestRunRequest(BaseModel):
    version_id: int | None = None
    initial_equity: float = 10_000
    fee_pct: float = 0.1
    slippage_pct: float = 0.05
    limit: int = 500


def model_payload(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@router.get("")
def bots(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    try:
        return list_saved_bots(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("")
def create_bot(payload: BotCreateRequest) -> dict:
    try:
        return create_saved_bot(payload=model_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/backtests")
def all_bot_backtests(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    try:
        return list_saved_bot_backtests(bot_id=None, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{bot_id}")
def bot_detail(bot_id: int) -> dict:
    try:
        return get_saved_bot(bot_id=bot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{bot_id}/backtests")
def bot_backtests(bot_id: int, limit: int = Query(default=50, ge=1, le=500)) -> dict:
    try:
        return list_saved_bot_backtests(bot_id=bot_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{bot_id}/backtests")
def run_bot_backtest(bot_id: int, payload: BacktestRunRequest) -> dict:
    try:
        return run_saved_bot_backtest(bot_id=bot_id, **model_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/backtests/{backtest_id}")
def bot_backtest_detail(backtest_id: int) -> dict:
    try:
        return get_saved_bot_backtest(backtest_id=backtest_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{bot_id}/versions")
def bot_version(bot_id: int, payload: BotVersionRequest) -> dict:
    try:
        return create_saved_bot_version(bot_id=bot_id, payload=model_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
