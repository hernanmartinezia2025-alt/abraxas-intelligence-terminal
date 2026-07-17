from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from backend.app.services.chart_indicator_service import (
    archive_workspace_preset,
    compute_chart_workspace,
    save_workspace_preset,
    workspace_presets,
)

router = APIRouter(prefix="/api/chart-indicators", tags=["chart-indicators"])


class IndicatorConfig(BaseModel):
    id: str | None = Field(default=None, max_length=48)
    kind: str = Field(pattern="^(sma|ema|bollinger)$")
    period: int = Field(ge=2, le=500)
    deviation: float = Field(default=2.0, ge=0.1, le=10)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    line_width: int = Field(default=2, ge=1, le=4)
    label: str | None = Field(default=None, max_length=80)
    visible: bool = True


class WorkspaceRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", min_length=3, max_length=24)
    timeframe: str = Field(default="15m", pattern="^(1m|5m|15m|1h|4h|1d|1w)$")
    limit: int = Field(default=300, ge=50, le=2000)
    indicators: list[IndicatorConfig] = Field(min_length=1, max_length=8)


class PresetRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    symbol: str = Field(default="BTCUSDT", min_length=3, max_length=24)
    timeframe: str = Field(default="15m", pattern="^(1m|5m|15m|1h|4h|1d|1w)$")
    indicators: list[IndicatorConfig] = Field(min_length=1, max_length=8)


def values(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def indicator_values(items: list[IndicatorConfig]) -> list[dict]:
    return [values(item) for item in items]


@router.post("/compute")
def compute(payload: WorkspaceRequest) -> dict:
    data = values(payload)
    try:
        return compute_chart_workspace(
            data["symbol"], data["timeframe"], data["limit"], indicator_values(payload.indicators)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/presets")
def presets(
    symbol: str = Query(default="", max_length=24),
    timeframe: str = Query(default="", max_length=8),
    include_archived: bool = Query(default=False),
) -> dict:
    return workspace_presets(symbol, timeframe, include_archived)


@router.post("/presets")
def save_preset(payload: PresetRequest) -> dict:
    data = values(payload)
    try:
        return save_workspace_preset(
            data["name"], data["symbol"], data["timeframe"], indicator_values(payload.indicators)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/presets/{preset_id}")
def archive_preset(preset_id: int = Path(ge=1)) -> dict:
    try:
        return archive_workspace_preset(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
