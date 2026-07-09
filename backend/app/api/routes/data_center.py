from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from backend.app.services.data_center_service import (
    export_dataset_csv,
    get_data_catalog,
    get_data_datasets,
    get_data_health,
    get_data_sources,
    get_dataset_preview,
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


@router.get("/datasets/{dataset_id}/preview")
def data_dataset_preview(dataset_id: str, limit: int = 25) -> dict:
    return get_dataset_preview(dataset_id=dataset_id, limit=max(1, min(limit, 200)))


@router.get("/export/{dataset_id}.csv")
def data_dataset_export(dataset_id: str, limit: int = 5000) -> Response:
    csv_payload = export_dataset_csv(dataset_id=dataset_id, limit=max(1, min(limit, 50000)))
    return Response(
        content=csv_payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}.csv"'},
    )
