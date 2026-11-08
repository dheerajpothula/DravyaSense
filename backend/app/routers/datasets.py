"""
Datasets router — /api/datasets

Endpoints:
  POST   /api/datasets/upload        — Upload CSV / XLSX, get column analysis
  GET    /api/datasets               — List all uploaded datasets
  GET    /api/datasets/{id}          — Dataset detail (incl. column roles)
  PUT    /api/datasets/{id}/roles    — Confirm / correct column roles
  GET    /api/datasets/{id}/preview  — Paginated raw data preview
  DELETE /api/datasets/{id}          — Delete dataset + file
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.dataset import (
    DatasetDetail,
    DatasetPreview,
    DatasetSummary,
    DeleteResponse,
    RoleConfirmRequest,
    UploadAnalysis,
)
from app.services import dataset_service

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post(
    "/upload",
    response_model=UploadAnalysis,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a sensor dataset file",
)
async def upload_dataset(
    file: UploadFile = File(..., description="CSV or XLSX sensor file"),
    db:   AsyncSession = Depends(get_db),
) -> UploadAnalysis:
    """
    Upload a CSV or Excel file containing electronic-tongue sensor readings.

    - Validates file type and size.
    - Saves the raw file to disk (never modified).
    - Detects column roles (sensor / sample_id / category / ignored).
    - Persists dataset metadata to the database.
    - Returns analysis results including detected column roles and warnings.
    """
    try:
        return await dataset_service.process_upload(file, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Unexpected error during upload: {exc}") from exc


@router.get(
    "",
    response_model=list[DatasetSummary],
    summary="List all uploaded datasets",
)
async def list_datasets(
    db: AsyncSession = Depends(get_db),
) -> list[DatasetSummary]:
    return await dataset_service.list_datasets(db)


@router.get(
    "/{dataset_id}",
    response_model=DatasetDetail,
    summary="Get dataset detail",
)
async def get_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> DatasetDetail:
    try:
        return await dataset_service.get_dataset_detail(dataset_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc


@router.put(
    "/{dataset_id}/roles",
    response_model=DatasetDetail,
    summary="Confirm or correct column role assignments",
)
async def confirm_column_roles(
    dataset_id: str,
    body:       RoleConfirmRequest,
    db:         AsyncSession = Depends(get_db),
) -> DatasetDetail:
    """
    Persist the user's confirmed (or corrected) column role assignments.
    Sensor columns are the only columns that will enter the feature matrix
    for PCA and t-SNE.  Category labels are preserved as metadata only.
    """
    try:
        return await dataset_service.confirm_roles(dataset_id, body.column_roles, db)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc


@router.get(
    "/{dataset_id}/preview",
    response_model=DatasetPreview,
    summary="Paginated raw data preview",
)
async def preview_dataset(
    dataset_id: str,
    page:       int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size:  int = Query(default=20, ge=5, le=100, description="Rows per page"),
    db:         AsyncSession = Depends(get_db),
) -> DatasetPreview:
    try:
        return await dataset_service.get_preview(dataset_id, page, page_size, db)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc


@router.delete(
    "/{dataset_id}",
    response_model=DeleteResponse,
    summary="Delete a dataset",
)
async def delete_dataset(
    dataset_id: str,
    db:         AsyncSession = Depends(get_db),
) -> DeleteResponse:
    try:
        deleted_id = await dataset_service.delete_dataset(dataset_id, db)
        return DeleteResponse(
            deleted_id=deleted_id,
            message="Dataset deleted successfully.",
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
