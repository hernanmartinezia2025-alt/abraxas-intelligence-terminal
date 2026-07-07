from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"ok": True, "service": "ABRAXAS Intelligence Terminal API", "version": "v1"}