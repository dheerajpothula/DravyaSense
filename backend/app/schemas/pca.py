"""
Pydantic schemas for the PCA Analysis API (Module 04).

All numerical results contain only values computed by sklearn.decomposition.PCA
applied to the actual feature matrix.  No example or fabricated values are ever
returned.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

# ── Input types ───────────────────────────────────────────────────

InputType = Literal["raw_dataset", "processed_dataset"]


# ── Run / Save request ────────────────────────────────────────────

class PcaRunRequest(BaseModel):
    """
    Request body for both /run (no save) and /save (persist experiment).

    input_type:
      "raw_dataset"       — use a Dataset record; feature columns are those
                            with role="sensor" in column_roles JSON.
      "processed_dataset" — use a ProcessedDataset record; feature columns
                            are those in selected_features JSON.

    n_components:
      Number of principal components to compute.  Capped at
      min(n_samples, n_features) by the engine.  Minimum 2.

    feature_columns:
      Optional explicit override of which columns enter the feature matrix.
      If omitted, all sensor/selected columns from the input record are used.
      sample_id and category columns are excluded even if listed here.

    experiment_name:
      Optional user-supplied label for saved experiments.
    """
    input_type:       InputType
    input_id:         str
    n_components:     int             = 4
    feature_columns:  list[str] | None = None   # None = use all sensor columns
    experiment_name:  str | None       = None

    @field_validator("n_components")
    @classmethod
    def n_components_at_least_two(cls, v: int) -> int:
        if v < 2:
            raise ValueError("n_components must be at least 2.")
        return v


# ── PCA result ────────────────────────────────────────────────────

class PcaResult(BaseModel):
    """
    Full PCA computation result.

    Returned by /run (unsaved) and /save (persisted).
    When unsaved, experiment_id is None.
    """
    experiment_id:   str | None   # None for /run; UUID for /save

    # ── Provenance ────────────────────────────────────────────
    input_type:             InputType
    input_id:               str
    source_filename:        str
    preprocessing_summary:  str | None
    experiment_name:        str | None

    # ── Feature matrix description ────────────────────────────
    n_samples:       int
    n_features:      int
    n_components:    int           # actual computed (may be less than requested)
    feature_columns: list[str]

    # ── Metadata (never in feature matrix) ────────────────────
    sample_ids:      list[str]
    category_labels: list[str]     # empty list when no category column
    category_column: str | None

    # ── Variance ──────────────────────────────────────────────
    explained_variance_ratio:  list[float]   # length = n_components
    cumulative_variance_ratio: list[float]   # length = n_components, monotone ↑

    # ── Numerical results ─────────────────────────────────────
    scores:   list[list[float]]   # [n_samples][n_components]  — PC coordinates
    loadings: list[list[float]]   # [n_components][n_features] — eigenvectors

    # ── Reproducibility + diagnostics ─────────────────────────
    sklearn_version: str
    warnings:        list[str]
    created_at:      datetime | None   # None for unsaved /run results


# ── Experiment listing ────────────────────────────────────────────

class PcaExperimentSummary(BaseModel):
    """Lightweight listing item for the experiment history sidebar."""
    model_config = ConfigDict(from_attributes=True)

    id:                       str
    experiment_name:          str | None
    input_type:               str
    input_id:                 str
    source_filename:          str
    preprocessing_summary:    str | None
    n_samples:                int
    n_features:               int
    n_components:             int
    explained_variance_ratio: str   # JSON list — parse client-side
    sklearn_version:          str
    created_at:               datetime


class DeletePcaResponse(BaseModel):
    deleted_id: str
    message:    str
