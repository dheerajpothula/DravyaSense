"""
t-SNE router — /api/tsne

Endpoints
─────────
  POST   /api/tsne/run               — Compute t-SNE, return result, no DB record
  POST   /api/tsne/save              — Compute t-SNE and persist experiment
  GET    /api/tsne/experiments       — List saved experiments
  GET    /api/tsne/experiments/{id}  — Get full experiment result
  DELETE /api/tsne/experiments/{id}  — Delete experiment (source unchanged)

Scientific note
───────────────
t-SNE preserves LOCAL neighbourhood structure.  Visual proximity in the
embedding reflects similarity in the original feature space.  Distances
BETWEEN clusters are not directly interpretable.  Category labels are
never passed to the t-SNE algorithm — they are metadata used only for
visualisation colouring and post-analysis evaluation.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.tsne import (
    DeleteTsneResponse,
    TsneExperimentSummary,
    TsneResult,
    TsneRunRequest,
)
from app.services import tsne_service

router = APIRouter(prefix="/api/tsne", tags=["tsne"])


@router.post(
    "/run",
    response_model=TsneResult,
    summary="Compute t-SNE without saving",
)
async def run_tsne(
    body: TsneRunRequest,
    db:   AsyncSession = Depends(get_db),
) -> TsneResult:
    """
    Compute t-SNE on the specified raw or processed dataset and return
    the full embedding.  Nothing is written to the database — use /save
    to persist the experiment.

    sample_id and category columns are never included in the feature matrix.
    Zero-variance features are excluded with a warning.
    NaN or infinity values raise HTTP 422.
    Perplexity must be < n_samples (validated dynamically).

    t-SNE preserves local neighbourhood structure.  Distances between
    clusters in the embedding are NOT directly interpretable.
    """
    try:
        return await tsne_service.run_tsne(body, db)
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
    response_model=TsneResult,
    status_code=status.HTTP_201_CREATED,
    summary="Compute t-SNE and save experiment",
)
async def save_tsne(
    body: TsneRunRequest,
    db:   AsyncSession = Depends(get_db),
) -> TsneResult:
    """
    Compute t-SNE on the specified dataset, persist a TsneExperiment
    record, and return the full result with experiment_id populated.

    All effective hyperparameters (including the resolved learning rate)
    are stored so the experiment can be reproduced exactly.

    The source dataset and processed dataset files are never modified.
    """
    try:
        return await tsne_service.save_tsne(body, db)
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
    response_model=list[TsneExperimentSummary],
    summary="List saved t-SNE experiments",
)
async def list_experiments(
    source_id:  str | None = Query(default=None,
                                   description="Filter by input_id"),
    input_type: str | None = Query(default=None,
                                   description="Filter by input_type: "
                                               "raw_dataset | processed_dataset"),
    db: AsyncSession = Depends(get_db),
) -> list[TsneExperimentSummary]:
    """
    List all saved t-SNE experiments, most recent first.
    Optionally filter by source_id or input_type.
    """
    return await tsne_service.list_experiments(db, source_id, input_type)


@router.get(
    "/experiments/{experiment_id}",
    response_model=TsneResult,
    summary="Get full t-SNE experiment result",
)
async def get_experiment(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
) -> TsneResult:
    """
    Retrieve a saved t-SNE experiment including embedding coordinates,
    sample IDs, category labels, and all stored hyperparameters.
    """
    try:
        return await tsne_service.get_experiment(experiment_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc


@router.delete(
    "/experiments/{experiment_id}",
    response_model=DeleteTsneResponse,
    summary="Delete a t-SNE experiment",
)
async def delete_experiment(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
) -> DeleteTsneResponse:
    """
    Delete a saved t-SNE experiment record.
    The source dataset and processed dataset files are never affected.
    """
    try:
        deleted_id = await tsne_service.delete_experiment(experiment_id, db)
        return DeleteTsneResponse(
            deleted_id=deleted_id,
            message="t-SNE experiment deleted successfully.",
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
