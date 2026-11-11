"""
t-SNE service — computation and experiment persistence.

Design principles
─────────────────
• All embedding coordinates come from sklearn.manifold.TSNE applied to
  the real feature matrix.  No fabricated values are ever returned.

• sample_id and category columns are excluded from the feature matrix by
  feature_loader._build_bundle().  This guarantee is tested in the t-SNE
  test suite and is shared with the PCA service.

• Processed datasets are loaded as-is — no additional scaling is applied
  here.  Using a processed dataset with this service does NOT double-scale
  the data.

• Perplexity is validated against the actual sample count before sklearn
  is called:  1 ≤ perplexity < n_samples.

• learning_rate="auto" is resolved to
      max(n_samples / (early_exaggeration * 4), 50)
  per sklearn 1.5.2.  The resolved float is recorded in the experiment,
  never the string "auto".  When the fitted estimator exposes a
  learning_rate_ attribute, that authoritative value is used.

• max_iter is used (not the deprecated n_iter parameter).

• random_state is required for saved experiments.  Two runs with the same
  seed, same data and same hyperparameters will produce identical embeddings.

• The TsneExperiment record stores all arrays as JSON text — no sklearn
  objects are ever pickled.

• t-SNE preserves local neighbourhood structure.  Distances BETWEEN
  clusters are NOT directly interpretable.  This caveat is documented
  here and surfaced to users by the frontend.

Scientific note on learning-rate resolution
────────────────────────────────────────────
sklearn 1.5.2 resolves learning_rate="auto" as:
    max(n / (early_exaggeration * 4), 50)
where n = n_samples and early_exaggeration defaults to 12.0, giving:
    max(n / 48, 50)
Reference: sklearn source sklearn/manifold/_t_sne.py, _fit() method.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import sklearn
from sklearn.manifold import TSNE
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tsne_experiment import TsneExperiment
from app.schemas.tsne import (
    DeleteTsneResponse,
    TsneExperimentSummary,
    TsneResult,
    TsneRunRequest,
)
from app.services.feature_loader import (
    FeatureBundle,
    load_processed_dataset,
    load_raw_dataset,
)


# ─────────────────────────────────────────────────────────────────
# Core t-SNE computation
# ─────────────────────────────────────────────────────────────────

def _compute_tsne(
    bundle: FeatureBundle,
    req: TsneRunRequest,
) -> dict[str, Any]:
    """
    Run sklearn TSNE on the feature bundle and return a dict of all
    results including the resolved learning rate.

    Parameters
    ----------
    bundle :
        Validated, metadata-free feature matrix from feature_loader.
    req :
        User-supplied hyperparameters.

    Returns
    -------
    dict with keys:
        embedding            — list[list[float]], shape (n_samples, n_components)
        learning_rate        — float, resolved value
        warnings             — list[str]

    Raises
    ------
    ValueError
        If perplexity ≥ n_samples, or if any other sklearn-level
        constraint is violated.
    """
    n_samples, n_features = bundle.feature_matrix.shape
    warnings_out = list(bundle.warnings)

    # ── Validate perplexity ──────────────────────────────────────
    if req.perplexity >= n_samples:
        raise ValueError(
            f"Perplexity ({req.perplexity}) must be strictly less than "
            f"n_samples ({n_samples}).  "
            f"Recommended range: 5 \u2264 perplexity \u2264 {max(5, n_samples // 3)}."
        )
    if req.perplexity < 1.0:
        raise ValueError(
            f"Perplexity ({req.perplexity}) must be \u2265 1.0."
        )

    # ── Resolve learning rate ────────────────────────────────────
    # sklearn 1.5.2 auto formula: max(n / (early_exaggeration * 4), 50)
    if req.learning_rate == "auto":
        lr_resolved = float(max(n_samples / (req.early_exaggeration * 4), 50.0))
    else:
        lr_resolved = float(req.learning_rate)

    # ── Build and run TSNE ───────────────────────────────────────
    tsne = TSNE(
        n_components=req.n_components,
        perplexity=req.perplexity,
        early_exaggeration=req.early_exaggeration,
        learning_rate=lr_resolved,
        max_iter=req.max_iter,
        random_state=req.random_state,
        metric=req.metric,
        init=req.init,
        method="barnes_hut" if req.n_components <= 3 else "exact",
        verbose=0,
    )

    embedding_arr: np.ndarray = tsne.fit_transform(bundle.feature_matrix)

    # ── Use authoritative learning_rate_ if available ────────────
    # sklearn 1.5.2 exposes learning_rate_ on the fitted estimator.
    if hasattr(tsne, "learning_rate_"):
        lr_resolved = float(tsne.learning_rate_)

    return {
        "embedding":     [[float(v) for v in row] for row in embedding_arr],
        "learning_rate": lr_resolved,
        "warnings":      warnings_out,
    }


# ─────────────────────────────────────────────────────────────────
# Public API: run (no save)
# ─────────────────────────────────────────────────────────────────

async def run_tsne(
    request: TsneRunRequest,
    db: AsyncSession,
) -> TsneResult:
    """
    Compute t-SNE and return the result.  Nothing is written to the
    database — use /save to persist the experiment.
    """
    bundle = await _load_bundle(request, db)
    result = _compute_tsne(bundle, request)

    return TsneResult(
        experiment_id=None,
        input_type=request.input_type,
        input_id=request.input_id,
        source_filename=bundle.source_filename,
        preprocessing_summary=bundle.preprocessing_summary,
        experiment_name=request.experiment_name,
        n_samples=bundle.feature_matrix.shape[0],
        n_features=bundle.feature_matrix.shape[1],
        n_components=request.n_components,
        feature_columns=bundle.feature_columns,
        sample_ids=bundle.sample_ids,
        category_labels=bundle.category_labels,
        category_column=bundle.category_column,
        perplexity=request.perplexity,
        learning_rate=result["learning_rate"],
        early_exaggeration=request.early_exaggeration,
        max_iter=request.max_iter,
        random_state=request.random_state,
        metric=request.metric,
        init=request.init,
        embedding=result["embedding"],
        sklearn_version=sklearn.__version__,
        warnings=result["warnings"],
        created_at=None,
    )


# ─────────────────────────────────────────────────────────────────
# Public API: save
# ─────────────────────────────────────────────────────────────────

async def save_tsne(
    request: TsneRunRequest,
    db: AsyncSession,
) -> TsneResult:
    """
    Compute t-SNE, persist a TsneExperiment record, and return the
    result with experiment_id populated.
    """
    bundle = await _load_bundle(request, db)
    result = _compute_tsne(bundle, request)

    experiment = TsneExperiment(
        experiment_name=request.experiment_name,
        input_type=request.input_type,
        input_id=request.input_id,
        source_filename=bundle.source_filename,
        preprocessing_summary=bundle.preprocessing_summary,
        n_samples=bundle.feature_matrix.shape[0],
        n_features=bundle.feature_matrix.shape[1],
        feature_columns=json.dumps(bundle.feature_columns),
        sample_ids=json.dumps(bundle.sample_ids),
        category_labels=json.dumps(bundle.category_labels),
        category_column=bundle.category_column,
        n_components=request.n_components,
        perplexity=request.perplexity,
        learning_rate=result["learning_rate"],
        early_exaggeration=request.early_exaggeration,
        max_iter=request.max_iter,
        random_state=request.random_state,
        metric=request.metric,
        init=request.init,
        embedding=json.dumps(result["embedding"]),
        sklearn_version=sklearn.__version__,
        warnings=json.dumps(result["warnings"]),
    )
    db.add(experiment)
    await db.commit()
    await db.refresh(experiment)

    return TsneResult(
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
        perplexity=experiment.perplexity,
        learning_rate=experiment.learning_rate,
        early_exaggeration=experiment.early_exaggeration,
        max_iter=experiment.max_iter,
        random_state=experiment.random_state,
        metric=experiment.metric,
        init=experiment.init,
        embedding=result["embedding"],
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
) -> list[TsneExperimentSummary]:
    """
    List saved t-SNE experiments, ordered most-recent first.
    Optionally filter by input_id (source or processed dataset UUID)
    or input_type.
    """
    stmt = select(TsneExperiment).order_by(TsneExperiment.created_at.desc())
    if source_id is not None:
        stmt = stmt.where(TsneExperiment.input_id == source_id)
    if input_type is not None:
        stmt = stmt.where(TsneExperiment.input_type == input_type)

    result = await db.execute(stmt)
    return [TsneExperimentSummary.model_validate(e) for e in result.scalars().all()]


async def get_experiment(
    experiment_id: str,
    db: AsyncSession,
) -> TsneResult:
    """Retrieve and deserialise a saved t-SNE experiment."""
    exp = await _get_experiment_or_404(experiment_id, db)

    return TsneResult(
        experiment_id=exp.id,
        input_type=exp.input_type,          # type: ignore[arg-type]
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
        perplexity=exp.perplexity,
        learning_rate=exp.learning_rate,
        early_exaggeration=exp.early_exaggeration,
        max_iter=exp.max_iter,
        random_state=exp.random_state,
        metric=exp.metric,
        init=exp.init,
        embedding=json.loads(exp.embedding),
        sklearn_version=exp.sklearn_version,
        warnings=json.loads(exp.warnings),
        created_at=exp.created_at,
    )


async def delete_experiment(
    experiment_id: str,
    db: AsyncSession,
) -> str:
    """Delete a t-SNE experiment record.  Source dataset is never affected."""
    await _get_experiment_or_404(experiment_id, db)
    await db.execute(
        delete(TsneExperiment).where(TsneExperiment.id == experiment_id)
    )
    await db.commit()
    return experiment_id


# ─────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────

async def _load_bundle(
    request: TsneRunRequest,
    db: AsyncSession,
) -> FeatureBundle:
    """Dispatch to the correct feature loader based on input_type."""
    if request.input_type == "raw_dataset":
        return await load_raw_dataset(request.input_id, request.feature_columns, db)
    elif request.input_type == "processed_dataset":
        return await load_processed_dataset(request.input_id, request.feature_columns, db)
    else:
        raise ValueError(
            f"Unknown input_type '{request.input_type}'. "
            f"Must be 'raw_dataset' or 'processed_dataset'."
        )


async def _get_experiment_or_404(
    experiment_id: str,
    db: AsyncSession,
) -> TsneExperiment:
    result = await db.execute(
        select(TsneExperiment).where(TsneExperiment.id == experiment_id)
    )
    exp = result.scalar_one_or_none()
    if exp is None:
        raise LookupError(f"t-SNE experiment '{experiment_id}' not found.")
    return exp
