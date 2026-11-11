"""
Pydantic schemas for the Preprocessing Studio API.

Phase 1: data-quality analysis and outlier detection.
Phase 2: preprocessing configuration, preview, and processed-dataset persistence.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


# ── Data quality ──────────────────────────────────────────────────

class ColumnQuality(BaseModel):
    """Quality metrics for a single sensor column."""
    column:         str
    missing_count:  int      # NaN values
    missing_pct:     float   # missing_count / row_count × 100
    invalid_count:  int      # non-finite (inf / -inf), excluding NaN
    invalid_pct:     float   # invalid_count / row_count × 100
    unique_count:   int


class QualityReport(BaseModel):
    """Overall data-quality summary for a dataset."""
    dataset_id:           str
    dataset_name:         str
    row_count:            int
    sensor_columns:       list[str]
    total_missing:        int
    total_invalid:        int
    duplicate_rows:       int          # rows with identical sensor readings
    duplicate_sample_ids: list[str]    # sample IDs of duplicate rows
    columns:              list[ColumnQuality]


# ── Outlier detection ─────────────────────────────────────────────

class IQROutliers(BaseModel):
    """IQR-based outlier analysis for one sensor column."""
    q1:                 float
    q3:                 float
    iqr:                float
    lower_bound:        float          # Q1 − multiplier × IQR
    upper_bound:        float          # Q3 + multiplier × IQR
    outlier_count:      int
    outlier_sample_ids: list[str]


class ZScoreOutliers(BaseModel):
    """Z-score-based outlier analysis for one sensor column."""
    mean:               float
    std:                float
    threshold:          float
    outlier_count:      int
    outlier_sample_ids: list[str]


class SensorOutlierReport(BaseModel):
    """Combined IQR + Z-score outlier report for one sensor column."""
    column:  str
    iqr:     IQROutliers
    zscore:  ZScoreOutliers


class OutlierReport(BaseModel):
    """Outlier analysis for all sensor columns in a dataset."""
    dataset_id:         str
    dataset_name:       str
    row_count:          int
    sensor_columns:     list[str]
    iqr_multiplier:     float
    zscore_threshold:   float
    outliers:           list[SensorOutlierReport]


# ═══════════════════════════════════════════════════════════════════
# Phase 2 — Preprocessing configuration & processed datasets
# ═══════════════════════════════════════════════════════════════════

ImputationStrategy = Literal["mean", "median", "none"]
ScalingMethod      = Literal["standard", "minmax", "robust", "none"]
OutlierAction      = Literal["keep", "clip", "remove"]


class PreprocessingConfig(BaseModel):
    """
    Full preprocessing pipeline configuration.
    Stored as readable JSON — never a pickled sklearn Pipeline.

    All transformations apply only to `selected_features` (which must
    be a subset of the dataset's sensor columns).  Metadata columns
    (sample_id, category) are never transformed.
    """
    selected_features:   list[str]
    imputation_strategy: ImputationStrategy = "none"
    scaling_method:      ScalingMethod      = "none"
    outlier_action:      OutlierAction      = "keep"
    iqr_multiplier:      float              = 1.5

    @field_validator("selected_features")
    @classmethod
    def features_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one sensor column must be selected.")
        return v

    @field_validator("iqr_multiplier")
    @classmethod
    def multiplier_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("iqr_multiplier must be positive.")
        return v


class PreviewRequest(BaseModel):
    """Request body for the preview endpoint (no data saved)."""
    dataset_id: str
    config:     PreprocessingConfig


class ApplyRequest(BaseModel):
    """Request body for the apply endpoint (saves processed data + record)."""
    dataset_id: str
    config:     PreprocessingConfig


# ── Preview response ──────────────────────────────────────────────

class ColumnStatsBeforeAfter(BaseModel):
    """Per-column statistics before and after preprocessing."""
    column:         str
    before_mean:    float | None
    before_std:     float | None
    before_min:     float | None
    before_max:     float | None
    before_missing: int
    after_mean:     float | None
    after_std:      float | None
    after_min:      float | None
    after_max:     float | None
    after_missing:  int


class PreviewResponse(BaseModel):
    """In-memory preview of preprocessing results — nothing is saved."""
    dataset_id:              str
    source_filename:         str
    row_count_before:       int
    row_count_after:        int
    columns:                 list[str]
    selected_features:      list[str]
    sample_id_column:       str | None
    category_columns:       list[str]
    preview_rows:           list[list[Any]]       # first 10 rows
    transformations_applied: list[str]
    warnings:                list[str]
    column_stats:           list[ColumnStatsBeforeAfter]
    # Units after transformation — selected features get updated labels;
    # unselected sensor columns retain their original source units.
    processed_column_units: dict[str, str]        # {col: unit_string}


# ── Processed dataset schemas ─────────────────────────────────────

class ProcessedDatasetSummary(BaseModel):
    """Lightweight listing item."""
    model_config = ConfigDict(from_attributes=True)

    id:                   str
    source_dataset_id:    str
    source_filename:       str
    row_count:             int
    sensor_column_count:   int
    selected_features:     str   # JSON list — parse with JSON.parse()
    sklearn_version:       str
    created_at:            datetime
    # Derived from pipeline_config JSON so the UI can distinguish
    # multiple processed versions of the same source dataset without
    # needing a full detail fetch.  Populated by the service layer.
    scaler_type:           str | None = None


class ProcessedDatasetDetail(BaseModel):
    """Full processed-dataset record."""
    model_config = ConfigDict(from_attributes=True)

    id:                      str
    source_dataset_id:       str
    source_filename:          str
    processed_filename:       str
    file_size_bytes:           int
    row_count:                int
    column_count:             int
    sensor_column_count:      int
    missing_value_count:      int
    selected_features:        str   # JSON list
    pipeline_config:          str   # JSON object
    transformations_applied:  str   # JSON list
    column_units:             str | None  # JSON object (copied from source)
    sklearn_version:          str
    created_at:               datetime
    # Derived from pipeline_config JSON — mirrors the summary field so
    # the frontend detail type (which extends the summary) is satisfied.
    scaler_type:               str | None = None


class ProcessedDatasetPreview(BaseModel):
    """Paginated preview of the processed data."""
    processed_id: str
    total_rows:   int
    page:         int
    page_size:    int
    columns:      list[str]
    rows:         list[list[Any]]


class DeleteProcessedResponse(BaseModel):
    deleted_id: str
    message:    str
