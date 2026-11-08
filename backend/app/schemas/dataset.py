"""
Pydantic schemas for the Dataset API.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

# ── Column role type ──────────────────────────────────────────────
ColumnRole = str  # "sensor" | "sample_id" | "category" | "ignored"

VALID_ROLES = {"sensor", "sample_id", "category", "ignored"}


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
    created_at:          datetime
    updated_at:          datetime


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
