"""
Pydantic schemas for the Dataset API.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

# ── Column role type ──────────────────────────────────────────────
ColumnRole = str  # "sensor" | "sample_id" | "category" | "ignored"

VALID_ROLES = {"sensor", "sample_id", "category", "ignored"}

# ── Measurement type enum ─────────────────────────────────────────
MeasurementType = Literal[
    "electronic_tongue",
    "electronic_nose",
    "chemical_analysis",
]

VALID_MEASUREMENT_TYPES: set[str] = {
    "electronic_tongue",
    "electronic_nose",
    "chemical_analysis",
}


# ── Upload response ───────────────────────────────────────────────

class ColumnInfo(BaseModel):
    """Metadata for a single detected column."""
    name:            str
    detected_role:   ColumnRole
    dtype:           str          # pandas dtype string
    missing_count:   int
    unique_count:    int
    sample_values:   list[Any]    # first ≤5 non-null values


class UploadAnalysis(BaseModel):
    """Returned immediately after file upload — before roles are confirmed."""
    dataset_id:   str
    filename:     str
    row_count:    int
    column_count: int
    columns:      list[ColumnInfo]
    missing_value_count: int
    warnings:     list[str]


# ── Role confirmation ─────────────────────────────────────────────

class RoleConfirmRequest(BaseModel):
    """User's confirmed/corrected column-role assignments."""
    column_roles: dict[str, ColumnRole]

    @field_validator("column_roles")
    @classmethod
    def validate_roles(cls, v: dict[str, ColumnRole]) -> dict[str, ColumnRole]:
        bad = {r for r in v.values() if r not in VALID_ROLES}
        if bad:
            raise ValueError(f"Invalid role(s): {bad}. Must be one of {VALID_ROLES}")
        return v


# ── Dataset read schemas ──────────────────────────────────────────

class DatasetSummary(BaseModel):
    """Lightweight listing item."""
    model_config = ConfigDict(from_attributes=True)

    id:                  str
    original_filename:   str
    file_size_bytes:     int
    row_count:           int
    column_count:        int
    sensor_column_count: int
    missing_value_count: int
    # Scientific metadata — included so the Data Explorer can classify
    # datasets correctly without requiring a second detail fetch.
    measurement_type:    str | None
    source_attribution:  str | None
    created_at:          datetime


class DatasetDetail(BaseModel):
    """Full dataset record including column roles."""
    model_config = ConfigDict(from_attributes=True)

    id:                  str
    original_filename:   str
    stored_filename:     str
    file_size_bytes:     int
    mime_type:           str
    row_count:           int
    column_count:        int
    sensor_column_count: int
    missing_value_count: int
    column_roles:        str   # raw JSON string — parsed client-side
    notes:               str | None
    # ── Scientific metadata ───────────────────────────────────
    measurement_type:    str | None  # electronic_tongue | electronic_nose | chemical_analysis
    source_attribution:  str | None  # research citation / DOI
    column_units:        str | None  # raw JSON {"col": "unit"} — parsed client-side
    created_at:          datetime
    updated_at:          datetime


# ── Scientific metadata update ────────────────────────────────────

class MetadataUpdateRequest(BaseModel):
    """
    Optional fields for updating scientific metadata on a dataset.
    All fields are optional — only supplied fields are changed.
    """
    measurement_type:   str | None = None
    source_attribution: str | None = None
    column_units:       dict[str, str] | None = None  # {column_name: unit_string}

    @field_validator("measurement_type")
    @classmethod
    def validate_measurement_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_MEASUREMENT_TYPES:
            raise ValueError(
                f"Invalid measurement_type '{v}'. "
                f"Must be one of {sorted(VALID_MEASUREMENT_TYPES)}."
            )
        return v


# ── Preview ───────────────────────────────────────────────────────

class DatasetPreview(BaseModel):
    """Paginated preview of the raw uploaded data."""
    dataset_id:   str
    total_rows:   int
    page:         int
    page_size:    int
    columns:      list[str]
    rows:         list[list[Any]]   # row-major, values as Python primitives


# ── Delete ────────────────────────────────────────────────────────

class DeleteResponse(BaseModel):
    deleted_id: str
    message:    str


# ── Statistics ────────────────────────────────────────────────────

class HistogramData(BaseModel):
    """Pre-computed histogram bins and frequencies for a sensor column."""
    bin_edges:    list[float]   # n+1 edges for n bins
    bin_centers:  list[float]   # n centers (midpoints of adjacent edges)
    frequencies:  list[int]      # n counts, one per bin


class SensorStatistics(BaseModel):
    """Descriptive statistics for a single sensor column."""
    column:         str
    count:          int
    mean:           float
    std:            float
    min:            float
    q1:             float       # 25th percentile
    median:         float       # 50th percentile
    q3:             float       # 75th percentile
    max:            float
    variance:       float
    skewness:       float
    kurtosis:       float       # excess kurtosis (Fisher's definition)
    missing_count:  int
    histogram:      HistogramData


class StatisticsResponse(BaseModel):
    """Per-sensor statistics for an uploaded dataset."""
    dataset_id:      str
    dataset_name:    str
    row_count:       int
    sensor_columns:  list[str]
    statistics:      list[SensorStatistics]
