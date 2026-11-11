"""
PCA router — /api/pca

Endpoints:
  POST   /api/pca/run                  — Compute PCA, return result, no DB record
  POST   /api/pca/save                 — Compute PCA and persist experiment
  GET    /api/pca/experiments          — List saved experiments
  GET    /api/pca/experiments/{id}     — Get full experiment result
  DELETE /api/pca/experiments/{id}     — Delete experiment (source unchanged)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.pca import (
    DeletePcaResponse,
    PcaExperimentSummary,
    PcaResult,
    PcaRunRequest,
)
from app.services import pca_service

router = APIRouter(prefix="/api/pca", tags=["pca"])


@router.post(
    "/run",
    response_model=PcaResult,
    summary="Compute PCA without saving",
)
async def run_pca(
    body: PcaRunRequest,
    db:   AsyncSession = Depends(get_db),
) -> PcaResult:
    """
    Compute PCA on the specified raw or processed dataset and return the
    full result.  Nothing is written to the database — use /save to
    persist the experiment.

    sample_id and category columns are never included in the feature matrix.
    Zero-variance features are excluded with a warning.
    NaN or infinity values raise HTTP 422.
    """
    try:
        return await pca_service.run_pca(body, db)
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
    "/save",
    response_model=PcaResult,
    status_code=status.HTTP_201_CREATED,
    summary="Compute PCA and save experiment",
)
async def save_pca(
    body: PcaRunRequest,
    db:   AsyncSession = Depends(get_db),
) -> PcaResult:
    """
    Compute PCA on the specified dataset and persist a PcaExperiment
    record.  Returns the full result with experiment_id populated.

    The source dataset and processed dataset files are never modified.
    """
    try:
        return await pca_service.save_pca(body, db)
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
    "/experiments",
    response_model=list[PcaExperimentSummary],
    summary="List saved PCA experiments",
)
async def list_experiments(
    source_id:  str | None = Query(default=None,
                                   description="Filter by input_id"),
    input_type: str | None = Query(default=None,
                                   description="Filter by input_type: "
                                               "raw_dataset | processed_dataset"),
    db: AsyncSession = Depends(get_db),
) -> list[PcaExperimentSummary]:
    """
    List all saved PCA experiments, most recent first.
    Optionally filter by `source_id` (input dataset / processed dataset UUID)
    or `input_type`.
    """
    return await pca_service.list_experiments(db, source_id, input_type)


@router.get(
    "/experiments/{experiment_id}",
    response_model=PcaResult,
    summary="Get full PCA experiment result",
)
async def get_experiment(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
) -> PcaResult:
    """
    Retrieve a saved PCA experiment including all numerical results:
    scores, loadings, explained variance, sample IDs and category labels.
    """
    try:
        return await pca_service.get_experiment(experiment_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc


@router.delete(
    "/experiments/{experiment_id}",
    response_model=DeletePcaResponse,
    summary="Delete a PCA experiment",
)
async def delete_experiment(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
) -> DeletePcaResponse:
    """
    Delete a saved PCA experiment record.
    The source dataset and processed dataset files are never affected.
    """
    try:
        deleted_id = await pca_service.delete_experiment(experiment_id, db)
        return DeletePcaResponse(
            deleted_id=deleted_id,
            message="PCA experiment deleted successfully.",
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
