from __future__ import annotations

from fastapi import APIRouter

from backend.app.services.data_center_service import (
    get_data_catalog,
    get_data_datasets,
    get_data_health,
    get_data_sources,
)

router = APIRouter(prefix="/api/data", tags=["data-center"])


@router.get("/catalog")
def data_catalog() -> dict:
    return get_data_catalog()


@router.get("/sources")
def data_sources() -> dict:
    return get_data_sources()


@router.get("/health")
def data_health() -> dict:
    return get_data_health()


@router.get("/datasets")
def data_datasets() -> dict:
    return get_data_datasets()
