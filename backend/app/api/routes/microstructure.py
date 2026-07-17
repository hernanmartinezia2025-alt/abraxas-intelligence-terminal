from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.microstructure_service import (
    capture_microstructure_window,
    microstructure_status,
    microstructure_trades,
)

router = APIRouter(prefix="/api/microstructure", tags=["microstructure"])


class CaptureRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", min_length=3, max_length=24)
    start_time: int = Field(gt=0)
    end_time: int = Field(gt=0)
    depth_limit: int = Field(default=100, ge=5, le=100)


def _payload(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@router.post("/capture")
def capture(payload: CaptureRequest) -> dict:
    try:
        return capture_microstructure_window(**_payload(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/status")
def status(symbol: str = Query(default="BTCUSDT", min_length=3, max_length=24)) -> dict:
    return microstructure_status(symbol)


@router.get("/trades")
def trades(
    symbol: str = Query(default="BTCUSDT", min_length=3, max_length=24),
    start_time: int = Query(gt=0),
    end_time: int = Query(gt=0),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict:
    return microstructure_trades(symbol, start_time, end_time, limit)
