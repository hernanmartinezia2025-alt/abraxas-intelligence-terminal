from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.storage.risk import get_risk_profile, set_kill_switch, update_risk_limits

router = APIRouter(prefix="/api/risk", tags=["risk"])


class RiskLimitsRequest(BaseModel):
    max_position_pct: float = Field(gt=0, le=100)
    max_daily_loss_pct: float = Field(gt=0, le=100)
    max_drawdown_pct: float = Field(gt=0, le=100)
    cooldown_minutes: int = Field(ge=0, le=10080)
    symbol_whitelist: list[str] = Field(min_length=1, max_length=100)


class KillSwitchRequest(BaseModel):
    active: bool
    reason: str = Field(min_length=3, max_length=500)


def model_payload(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@router.get("")
def risk_profile(audit_limit: int = Query(default=20, ge=1, le=200)) -> dict:
    return get_risk_profile(audit_limit=audit_limit)


@router.put("/limits")
def risk_limits(payload: RiskLimitsRequest) -> dict:
    try:
        return update_risk_limits(model_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/kill-switch")
def risk_kill_switch(payload: KillSwitchRequest) -> dict:
    try:
        values = model_payload(payload)
        return set_kill_switch(active=values["active"], reason=values["reason"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
