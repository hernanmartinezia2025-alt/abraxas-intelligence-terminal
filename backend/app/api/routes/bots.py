from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from backend.app.services.bot_service import (
    create_saved_bot,
    create_saved_bot_version,
    get_saved_bot_backtest,
    get_saved_bot,
    list_saved_bot_backtests,
    run_saved_bot_backtest,
    list_saved_bots,
    evaluate_saved_bot_signal,
    list_saved_bot_signals,
    create_saved_bot_paper_proposal,
    list_saved_bot_paper_proposals,
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
    version_id: int | None = Field(default=None, ge=1)
    initial_equity: float = Field(default=10_000, gt=0, le=1_000_000_000)
    fee_pct: float = Field(default=0.1, ge=0, le=5)
    slippage_pct: float = Field(default=0.05, ge=0, le=5)
    limit: int = Field(default=500, ge=60, le=1000)


class SignalEvaluationRequest(BaseModel):
    version_id: int | None = Field(default=None, ge=1)


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
def bot_detail(bot_id: int = Path(ge=1)) -> dict:
    try:
        return get_saved_bot(bot_id=bot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{bot_id}/backtests")
def bot_backtests(bot_id: int = Path(ge=1), limit: int = Query(default=50, ge=1, le=500)) -> dict:
    try:
        return list_saved_bot_backtests(bot_id=bot_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{bot_id}/backtests")
def run_bot_backtest(payload: BacktestRunRequest, bot_id: int = Path(ge=1)) -> dict:
    try:
        return run_saved_bot_backtest(bot_id=bot_id, **model_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/backtests/{backtest_id}")
def bot_backtest_detail(backtest_id: int = Path(ge=1)) -> dict:
    try:
        return get_saved_bot_backtest(backtest_id=backtest_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{bot_id}/versions")
def bot_version(payload: BotVersionRequest, bot_id: int = Path(ge=1)) -> dict:
    try:
        return create_saved_bot_version(bot_id=bot_id, payload=model_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{bot_id}/signals")
def bot_signals(bot_id: int = Path(ge=1), limit: int = Query(default=50, ge=1, le=500)) -> dict:
    try:
        return list_saved_bot_signals(bot_id=bot_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{bot_id}/signals/evaluate")
def evaluate_bot_signal(payload: SignalEvaluationRequest, bot_id: int = Path(ge=1)) -> dict:
    try:
        return evaluate_saved_bot_signal(bot_id=bot_id, **model_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{bot_id}/paper-proposals")
def bot_paper_proposals(bot_id: int = Path(ge=1), limit: int = Query(default=50, ge=1, le=500)) -> dict:
    try:
        return list_saved_bot_paper_proposals(bot_id=bot_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{bot_id}/signals/{evaluation_id}/paper-proposal")
def bot_paper_proposal(bot_id: int = Path(ge=1), evaluation_id: int = Path(ge=1)) -> dict:
    try:
        return create_saved_bot_paper_proposal(bot_id=bot_id, evaluation_id=evaluation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
