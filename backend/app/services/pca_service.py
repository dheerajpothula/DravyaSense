"""
PCA service — computation and experiment persistence.

Data loading and metadata-isolation are handled by the shared
feature_loader module, which is also used by the t-SNE service.

Design principles
─────────────────
• All results come from actual sklearn.decomposition.PCA applied to the
  real feature matrix.  No example or fabricated values are returned.

• sample_id and category columns are extracted as metadata BEFORE the
  feature matrix is assembled.  They never enter PCA.  This guarantee
  lives in feature_loader._build_bundle(), which is the single source
  of truth for both PCA and t-SNE.

• Processed datasets already have their scaling applied by Preprocessing
  Studio.  A human-readable preprocessing_summary records what was done.

• Zero-variance features are dropped with a warning rather than crashing.

• NaN and infinity values raise ValueError so the caller can surface a
  clear error to the user.

• n_components is capped at min(n_samples, n_features) so sklearn never
  receives an impossible request.

• The PcaExperiment record stores all arrays as JSON text — never a
  pickled sklearn object.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.decomposition import PCA
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pca_experiment import PcaExperiment
from app.schemas.pca import (
    DeletePcaResponse,
    PcaExperimentSummary,
    PcaResult,
    PcaRunRequest,
)

# ── Shared feature-loading utilities ─────────────────────────────
# These helpers are also used by tsne_service.  Keeping them in
# feature_loader ensures the metadata-isolation guarantee is
# enforced in exactly one place.
from app.services.feature_loader import (
    FeatureBundle as _FeatureBundle,
    load_raw_dataset      as _load_raw_dataset,
    load_processed_dataset as _load_processed_dataset,
)


# ─────────────────────────────────────────────────────────────────
# Core PCA computation
# ─────────────────────────────────────────────────────────────────

def _compute_pca(bundle: _FeatureBundle, n_components: int) -> dict[str, Any]:
    """
    Run sklearn PCA on the feature bundle and return a dict of all
    numerical results.  n_components is capped safely.
    """
    n_samples, n_features = bundle.feature_matrix.shape

    # Cap n_components to the maximum sklearn allows
    max_components = min(n_samples, n_features)
    actual_n = min(n_components, max_components)
    warnings = list(bundle.warnings)

    if actual_n < n_components:
        warnings.append(
            f"Requested {n_components} components, but data has "
            f"{n_samples} samples and {n_features} features. "
            f"n_components capped to {actual_n}."
        )

    pca = PCA(n_components=actual_n, svd_solver="full")
    scores_arr = pca.fit_transform(bundle.feature_matrix)  # (n_samples, actual_n)
    loadings_arr = pca.components_                          # (actual_n, n_features)

    evr = pca.explained_variance_ratio_.tolist()
    cumulative = list(np.cumsum(evr))

    return {
        "n_components":               actual_n,
        "explained_variance_ratio":   [float(v) for v in evr],
        "cumulative_variance_ratio":  [float(v) for v in cumulative],
        "scores":   [[float(v) for v in row] for row in scores_arr],
        "loadings": [[float(v) for v in row] for row in loadings_arr],
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────
# Public API: run (no save)
# ─────────────────────────────────────────────────────────────────

async def run_pca(
    request: PcaRunRequest,
    db: AsyncSession,
) -> PcaResult:
    """
    Compute PCA and return the result.  Nothing is written to the
    database — the caller gets a transient result.
    """
    bundle = await _load_bundle(request, db)
    result = _compute_pca(bundle, request.n_components)

    return PcaResult(
        experiment_id=None,
        input_type=request.input_type,
        input_id=request.input_id,
        source_filename=bundle.source_filename,
        preprocessing_summary=bundle.preprocessing_summary,
        experiment_name=request.experiment_name,
        n_samples=bundle.feature_matrix.shape[0],
        n_features=bundle.feature_matrix.shape[1],
        n_components=result["n_components"],
        feature_columns=bundle.feature_columns,
        sample_ids=bundle.sample_ids,
        category_labels=bundle.category_labels,
        category_column=bundle.category_column,
        explained_variance_ratio=result["explained_variance_ratio"],
        cumulative_variance_ratio=result["cumulative_variance_ratio"],
        scores=result["scores"],
        loadings=result["loadings"],
        sklearn_version=sklearn.__version__,
        warnings=result["warnings"],
        created_at=None,
    )


# ─────────────────────────────────────────────────────────────────
# Public API: save
# ─────────────────────────────────────────────────────────────────

async def save_pca(
    request: PcaRunRequest,
    db: AsyncSession,
) -> PcaResult:
    """
    Compute PCA, persist a PcaExperiment record, and return the result
    with experiment_id populated.
    """
    bundle = await _load_bundle(request, db)
    result = _compute_pca(bundle, request.n_components)

    experiment = PcaExperiment(
        experiment_name=request.experiment_name,
        input_type=request.input_type,
        input_id=request.input_id,
        source_filename=bundle.source_filename,
        preprocessing_summary=bundle.preprocessing_summary,
        n_samples=bundle.feature_matrix.shape[0],
        n_features=bundle.feature_matrix.shape[1],
        n_components=result["n_components"],
        feature_columns=json.dumps(bundle.feature_columns),
        sample_ids=json.dumps(bundle.sample_ids),
        category_labels=json.dumps(bundle.category_labels),
        category_column=bundle.category_column,
        explained_variance_ratio=json.dumps(result["explained_variance_ratio"]),
        cumulative_variance_ratio=json.dumps(result["cumulative_variance_ratio"]),
        scores=json.dumps(result["scores"]),
        loadings=json.dumps(result["loadings"]),
        sklearn_version=sklearn.__version__,
        warnings=json.dumps(result["warnings"]),
    )
    db.add(experiment)
    await db.commit()
    await db.refresh(experiment)

    return PcaResult(
        experiment_id=experiment.id,
        input_type=request.input_type,
        input_id=request.input_id,
        source_filename=bundle.source_filename,
        preprocessing_summary=bundle.preprocessing_summary,
        experiment_name=request.experiment_name,
        n_samples=experiment.n_samples,
        n_features=experiment.n_features,
        n_components=experiment.n_components,
        feature_columns=bundle.feature_columns,
        sample_ids=bundle.sample_ids,
        category_labels=bundle.category_labels,
        category_column=bundle.category_column,
        explained_variance_ratio=result["explained_variance_ratio"],
        cumulative_variance_ratio=result["cumulative_variance_ratio"],
        scores=result["scores"],
        loadings=result["loadings"],
        sklearn_version=sklearn.__version__,
        warnings=result["warnings"],
        created_at=experiment.created_at,
    )


# ─────────────────────────────────────────────────────────────────
# Public API: list / detail / delete
# ─────────────────────────────────────────────────────────────────

async def list_experiments(
    db: AsyncSession,
    source_id: str | None = None,
    input_type: str | None = None,
) -> list[PcaExperimentSummary]:
    """
    List saved PCA experiments, ordered most-recent first.
    Optionally filter by input_id (source dataset or processed dataset).
    """
    stmt = select(PcaExperiment).order_by(PcaExperiment.created_at.desc())
    if source_id is not None:
        stmt = stmt.where(PcaExperiment.input_id == source_id)
    if input_type is not None:
        stmt = stmt.where(PcaExperiment.input_type == input_type)

    result = await db.execute(stmt)
    return [PcaExperimentSummary.model_validate(e) for e in result.scalars().all()]


async def get_experiment(
    experiment_id: str,
    db: AsyncSession,
) -> PcaResult:
    """Retrieve and deserialise a saved PCA experiment."""
    exp = await _get_experiment_or_404(experiment_id, db)

    return PcaResult(
        experiment_id=exp.id,
        input_type=exp.input_type,  # type: ignore[arg-type]
        input_id=exp.input_id,
        source_filename=exp.source_filename,
        preprocessing_summary=exp.preprocessing_summary,
        experiment_name=exp.experiment_name,
        n_samples=exp.n_samples,
        n_features=exp.n_features,
        n_components=exp.n_components,
        feature_columns=json.loads(exp.feature_columns),
        sample_ids=json.loads(exp.sample_ids),
        category_labels=json.loads(exp.category_labels),
        category_column=exp.category_column,
        explained_variance_ratio=json.loads(exp.explained_variance_ratio),
        cumulative_variance_ratio=json.loads(exp.cumulative_variance_ratio),
        scores=json.loads(exp.scores),
        loadings=json.loads(exp.loadings),
        sklearn_version=exp.sklearn_version,
        warnings=json.loads(exp.warnings),
        created_at=exp.created_at,
    )


async def delete_experiment(
    experiment_id: str,
    db: AsyncSession,
) -> str:
    """Delete a PCA experiment record.  Source dataset is never affected."""
    await _get_experiment_or_404(experiment_id, db)  # raises 404 if missing
    await db.execute(
        delete(PcaExperiment).where(PcaExperiment.id == experiment_id)
    )
    await db.commit()
    return experiment_id


# ─────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────

async def _load_bundle(
    request: PcaRunRequest,
    db: AsyncSession,
) -> _FeatureBundle:
    """Dispatch to the correct loader based on input_type."""
    if request.input_type == "raw_dataset":
        return await _load_raw_dataset(request.input_id, request.feature_columns, db)
    elif request.input_type == "processed_dataset":
        return await _load_processed_dataset(request.input_id, request.feature_columns, db)
    else:
        raise ValueError(
            f"Unknown input_type '{request.input_type}'. "
            f"Must be 'raw_dataset' or 'processed_dataset'."
        )

async def _get_experiment_or_404(
    experiment_id: str,
    db: AsyncSession,
) -> PcaExperiment:
    result = await db.execute(
        select(PcaExperiment).where(PcaExperiment.id == experiment_id)
    )
    exp = result.scalar_one_or_none()
    if exp is None:
        raise LookupError(f"PCA experiment '{experiment_id}' not found.")
    return exp
