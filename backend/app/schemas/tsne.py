"""
Pydantic schemas for the t-SNE Analysis API (Module 05).

All numerical results contain only values computed by
sklearn.manifold.TSNE applied to the actual feature matrix.
No example or fabricated coordinates are ever returned.

Scientific note
───────────────
t-SNE preserves LOCAL neighbourhood structure.  Points that appear close
in the embedding were close in the original high-dimensional feature space.
However, the distances BETWEEN clusters are NOT directly interpretable —
they depend on the perplexity setting and the stochastic optimisation, not
on the actual inter-cluster distances in the original space.

Do not use t-SNE embedding coordinates to infer global structure or make
claims about absolute inter-category distances.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Shared input-type literal ─────────────────────────────────────
InputType = Literal["raw_dataset", "processed_dataset"]


# ── Run / Save request ────────────────────────────────────────────

class TsneRunRequest(BaseModel):
    """
    Request body for both /run (no save) and /save (persist experiment).

    input_type
        "raw_dataset"       — use a Dataset record (sensor-role columns)
        "processed_dataset" — use a ProcessedDataset record (selected_features)

    n_components
        2 for a 2-D embedding, 3 for a 3-D embedding.

    perplexity
        Controls the effective number of neighbours considered per point.
        Must satisfy 1.0 ≤ perplexity < n_samples.
        Recommended range: 5 ≤ perplexity ≤ n_samples / 3.
        The engine validates this against the actual sample count.

    learning_rate
        "auto" lets sklearn resolve the learning rate as
        max(n_samples / (early_exaggeration * 4), 50).
        A positive float overrides this.

    early_exaggeration
        Multiplier applied during the early exaggeration phase.
        Default 12.0 (sklearn default).

    max_iter
        Maximum number of optimisation iterations.  Minimum 250.

    random_state
        Integer seed for the stochastic optimisation.  Required for
        saved experiments; strongly recommended for all runs.

    metric
        Distance metric used to compute pairwise distances in the
        original space.  Default "euclidean".

    init
        Initialisation method.  "pca" (recommended — deterministic
        warm start) or "random".

    feature_columns
        Optional explicit list of columns to enter the feature matrix.
        Intersected with sensor / selected-feature columns.
        sample_id and category columns are excluded even if listed.

    experiment_name
        Optional user-supplied label for saved experiments.
    """
    input_type:          InputType
    input_id:            str
    n_components:        int   = Field(default=2,    ge=2, le=3)
    perplexity:          float = Field(default=30.0, gt=0.0)
    learning_rate:       float | Literal["auto"] = "auto"
    early_exaggeration:  float = Field(default=12.0, gt=0.0)
    max_iter:            int   = Field(default=1000, ge=250)
    random_state:        int   = Field(default=42)
    metric:              str   = "euclidean"
    init:                Literal["pca", "random"] = "pca"
    feature_columns:     list[str] | None = None
    experiment_name:     str | None = None

    @field_validator("n_components")
    @classmethod
    def n_components_valid(cls, v: int) -> int:
        if v not in (2, 3):
            raise ValueError("n_components must be 2 (2-D) or 3 (3-D).")
        return v

    @field_validator("learning_rate")
    @classmethod
    def learning_rate_valid(cls, v: float | str) -> float | str:
        if isinstance(v, str) and v != "auto":
            raise ValueError("learning_rate must be a positive number or 'auto'.")
        if isinstance(v, float) and v <= 0:
            raise ValueError("learning_rate must be positive.")
        return v


# ── t-SNE result ──────────────────────────────────────────────────

class TsneResult(BaseModel):
    """
    Full t-SNE computation result.

    Returned by /run (unsaved, experiment_id=None) and
    /save (persisted, experiment_id=UUID).

    Interpretation note
    ───────────────────
    t-SNE preserves local neighbourhood structure.  Proximity in the
    embedding reflects similarity in the original feature space.
    Inter-cluster distances in this plot are NOT directly interpretable.
    """
    experiment_id: str | None   # None for /run; UUID for /save

    # ── Provenance ────────────────────────────────────────────
    input_type:            InputType
    input_id:              str
    source_filename:       str
    preprocessing_summary: str | None
    experiment_name:       str | None

    # ── Feature matrix description ────────────────────────────
    n_samples:       int
    n_features:      int
    n_components:    int        # 2 or 3
    feature_columns: list[str]

    # ── Metadata (never in feature matrix) ────────────────────
    sample_ids:      list[str]
    category_labels: list[str]  # empty list when no category column
    category_column: str | None

    # ── t-SNE hyperparameters (effective values) ──────────────
    perplexity:          float
    learning_rate:       float   # resolved — never "auto"
    early_exaggeration:  float
    max_iter:            int
    random_state:        int
    metric:              str
    init:                str

    # ── Embedding coordinates ──────────────────────────────────
    # Shape: n_samples × n_components
    # Column order: [tsne_1, tsne_2] or [tsne_1, tsne_2, tsne_3]
    embedding: list[list[float]]

    # ── Reproducibility + diagnostics ─────────────────────────
    sklearn_version: str
    warnings:        list[str]
    created_at:      datetime | None   # None for unsaved /run results


# ── Experiment listing ────────────────────────────────────────────

class TsneExperimentSummary(BaseModel):
    """Lightweight listing item for the experiment history sidebar."""
    model_config = ConfigDict(from_attributes=True)

    id:                    str
    experiment_name:       str | None
    input_type:            str
    input_id:              str
    source_filename:       str
    preprocessing_summary: str | None
    n_samples:             int
    n_features:            int
    n_components:          int
    perplexity:            float
    learning_rate:         float
    early_exaggeration:    float
    max_iter:              int
    random_state:          int
    metric:                str
    init:                  str
    sklearn_version:       str
    created_at:            datetime


class DeleteTsneResponse(BaseModel):
    deleted_id: str
    message:    str
