"""
Preprocessing router — /api/preprocessing

Endpoints:
  POST   /api/preprocessing/preview                — Preview config in memory (no save)
  POST   /api/preprocessing/apply                   — Apply config, save processed data
  GET    /api/preprocessing/dataset/{dataset_id}   — List processed datasets for a source
  GET    /api/preprocessing/{processed_id}           — Get processed dataset detail
  GET    /api/preprocessing/{processed_id}/preview  — Paginated processed data
  DELETE /api/preprocessing/{processed_id}           — Delete processed dataset + file
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.preprocessing import (
    ApplyRequest,
    DeleteProcessedResponse,
    PreviewRequest,
    PreviewResponse,
    ProcessedDatasetDetail,
    ProcessedDatasetPreview,
    ProcessedDatasetSummary,
)
from app.services import preprocessing_service

router = APIRouter(prefix="/api/preprocessing", tags=["preprocessing"])


@router.post(
    "/preview",
    response_model=PreviewResponse,
    summary="Preview preprocessing results without saving",
)
async def preview_preprocessing(
    body: PreviewRequest,
    db:   AsyncSession = Depends(get_db),
) -> PreviewResponse:
    """
    Apply the preprocessing configuration to the source dataset in memory
    and return a preview of the results.  Nothing is saved to disk or the
    database — the caller can inspect the output before committing.

    Only sensor-role columns in `selected_features` are transformed.
    Metadata columns (sample_id, category) are preserved untouched.
    """
    try:
        return await preprocessing_service.preview_preprocessing(
            body.dataset_id, body.config, db,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc


@router.post(
    "/apply",
    response_model=ProcessedDatasetDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Apply preprocessing and save the processed dataset",
)
async def apply_preprocessing(
    body: ApplyRequest,
    db:   AsyncSession = Depends(get_db),
) -> ProcessedDatasetDetail:
    """
    Apply the preprocessing configuration to the source dataset, save the
    processed data as a CSV file, and persist a ProcessedDataset record.

    The original source file is never modified.  The pipeline configuration
    is stored as readable JSON (never a pickled sklearn Pipeline).
    """
    try:
        return await preprocessing_service.apply_preprocessing(
            body.dataset_id, body.config, db,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc


@router.get(
    "/dataset/{dataset_id}",
    response_model=list[ProcessedDatasetSummary],
    summary="List processed datasets for a source dataset",
)
async def list_processed_datasets(
    dataset_id: str,
    db:         AsyncSession = Depends(get_db),
) -> list[ProcessedDatasetSummary]:
    return await preprocessing_service.list_processed_datasets(dataset_id, db)


@router.get(
    "/{processed_id}",
    response_model=ProcessedDatasetDetail,
    summary="Get processed dataset detail",
)
async def get_processed_dataset(
    processed_id: str,
    db:           AsyncSession = Depends(get_db),
) -> ProcessedDatasetDetail:
    try:
        return await preprocessing_service.get_processed_detail(processed_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc


@router.get(
    "/{processed_id}/preview",
    response_model=ProcessedDatasetPreview,
    summary="Paginated preview of processed data",
)
async def preview_processed_dataset(
    processed_id: str,
    page:         int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size:    int = Query(default=20, ge=5, le=100, description="Rows per page"),
    db:           AsyncSession = Depends(get_db),
) -> ProcessedDatasetPreview:
    try:
        return await preprocessing_service.get_processed_preview(
            processed_id, page, page_size, db,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc


@router.delete(
    "/{processed_id}",
    response_model=DeleteProcessedResponse,
    summary="Delete a processed dataset",
)
async def delete_processed_dataset(
    processed_id: str,
    db:           AsyncSession = Depends(get_db),
) -> DeleteProcessedResponse:
    try:
        deleted_id = await preprocessing_service.delete_processed(processed_id, db)
        return DeleteProcessedResponse(
            deleted_id=deleted_id,
            message="Processed dataset deleted successfully.",
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
