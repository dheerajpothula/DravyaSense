"""
Dataset service — file I/O, parsing, DB persistence.

Responsibilities:
- Validate and save uploaded files to disk.
- Parse CSV / XLSX into a DataFrame for inspection.
- Run column detection heuristics.
- Persist and retrieve Dataset records via SQLAlchemy.
- Serve paginated preview data.
- Delete datasets (file + DB record).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.dataset import Dataset
from app.schemas.dataset import (
    ColumnInfo,
    DatasetDetail,
    DatasetPreview,
    DatasetSummary,
    UploadAnalysis,
)
from app.services.column_detector import (
    build_column_info,
    count_sensors,
    detect_column_roles,
)

settings = get_settings()

# Allowed MIME types and extensions
_ALLOWED_MIME = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_ALLOWED_EXT = {".csv", ".xlsx", ".xls"}

MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024


# ─────────────────────────────────────────────────────────────────
# Upload + parse
# ─────────────────────────────────────────────────────────────────

async def process_upload(
    file: UploadFile,
    db: AsyncSession,
) -> UploadAnalysis:
    """
    Validate, save and analyse an uploaded dataset file.
    Returns an UploadAnalysis with column detection results.
    The Dataset record is persisted to the database.
    """
    # ── 1. Validate extension ────────────────────────────────
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXT:
        raise ValueError(
            f"Unsupported file type '{suffix}'. "
            f"Please upload a CSV (.csv) or Excel (.xlsx) file."
        )

    # ── 2. Read content (enforce size limit) ──────────────────
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise ValueError(
            f"File exceeds the {settings.max_upload_size_mb} MB limit "
            f"({len(content) / 1_048_576:.1f} MB received)."
        )
    if len(content) == 0:
        raise ValueError("Uploaded file is empty.")

    # ── 3. Save raw file to disk (never modified afterwards) ──
    upload_dir: Path = settings.upload_dir_abs
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    file_path   = upload_dir / stored_name
    file_path.write_bytes(content)

    # ── 4. Parse into DataFrame ───────────────────────────────
    try:
        df = _parse_file(content, suffix)
    except Exception as exc:
        file_path.unlink(missing_ok=True)  # clean up on parse failure
        raise ValueError(f"Could not read file: {exc}") from exc

    if df.empty or len(df.columns) == 0:
        file_path.unlink(missing_ok=True)
        raise ValueError("File parsed successfully but contains no data or columns.")

    if len(df) < 2:
        file_path.unlink(missing_ok=True)
        raise ValueError(
            f"Dataset contains only {len(df)} row(s). "
            "A minimum of 2 rows is required for analysis."
        )

    # ── 5. Detect column roles ────────────────────────────────
    roles      = detect_column_roles(df)
    col_info   = build_column_info(df, roles)
    n_sensors  = count_sensors(roles)
    n_missing  = int(df.isna().sum().sum())

    # ── 6. Build warnings ─────────────────────────────────────
    warnings: list[str] = []
    if n_sensors == 0:
        warnings.append(
            "No sensor columns were automatically detected. "
            "Please assign column roles manually before running analysis."
        )
    if n_missing > 0:
        warnings.append(
            f"{n_missing} missing value(s) detected across the dataset. "
            "These will need to be handled in the Preprocessing Studio."
        )
    non_numeric_cols = [
        c["name"] for c in col_info if c["detected_role"] == "ignored"
    ]
    if non_numeric_cols:
        warnings.append(
            f"{len(non_numeric_cols)} column(s) could not be classified automatically "
            f"and are marked 'ignored': {', '.join(non_numeric_cols[:5])}"
            + (" …" if len(non_numeric_cols) > 5 else ".")
        )

    # ── 7. Persist Dataset record ─────────────────────────────
    mime = file.content_type or _guess_mime(suffix)
    dataset = Dataset(
        original_filename=file.filename or stored_name,
        stored_filename=stored_name,
        file_size_bytes=len(content),
        mime_type=mime,
        row_count=len(df),
        column_count=len(df.columns),
        column_roles=json.dumps(roles),
        missing_value_count=n_missing,
        sensor_column_count=n_sensors,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    return UploadAnalysis(
        dataset_id=dataset.id,
        filename=dataset.original_filename,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        columns=[ColumnInfo(**c) for c in col_info],
        missing_value_count=n_missing,
        warnings=warnings,
    )


def _parse_file(content: bytes, suffix: str) -> pd.DataFrame:
    import io
    if suffix == ".csv":
        # Try UTF-8 first, fall back to latin-1
        try:
            return pd.read_csv(io.BytesIO(content), encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(content), encoding="latin-1")
    else:
        return pd.read_excel(io.BytesIO(content), engine="openpyxl")


def _guess_mime(suffix: str) -> str:
    return {
        ".csv":  "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls":  "application/vnd.ms-excel",
    }.get(suffix, "application/octet-stream")


# ─────────────────────────────────────────────────────────────────
# Role confirmation
# ─────────────────────────────────────────────────────────────────

async def confirm_roles(
    dataset_id: str,
    roles: dict[str, str],
    db: AsyncSession,
) -> DatasetDetail:
    """Persist user-confirmed column roles and update sensor count."""
    dataset = await _get_or_404(dataset_id, db)

    n_sensors = sum(1 for r in roles.values() if r == "sensor")

    dataset.column_roles        = json.dumps(roles)
    dataset.sensor_column_count = n_sensors
    await db.commit()
    await db.refresh(dataset)

    return DatasetDetail.model_validate(dataset)


# ─────────────────────────────────────────────────────────────────
# List / detail / preview
# ─────────────────────────────────────────────────────────────────

async def list_datasets(db: AsyncSession) -> list[DatasetSummary]:
    result = await db.execute(
        select(Dataset).order_by(Dataset.created_at.desc())
    )
    return [DatasetSummary.model_validate(d) for d in result.scalars().all()]


async def get_dataset_detail(dataset_id: str, db: AsyncSession) -> DatasetDetail:
    dataset = await _get_or_404(dataset_id, db)
    return DatasetDetail.model_validate(dataset)


async def get_preview(
    dataset_id: str,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> DatasetPreview:
    """Return a paginated slice of the raw uploaded file."""
    dataset   = await _get_or_404(dataset_id, db)
    file_path = settings.upload_dir_abs / dataset.stored_filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Raw file for dataset '{dataset_id}' not found on disk. "
            "The file may have been moved or deleted outside the platform."
        )

    suffix = Path(dataset.stored_filename).suffix.lower()
    df = _parse_file(file_path.read_bytes(), suffix)

    total_rows = len(df)
    start = (page - 1) * page_size
    end   = start + page_size
    slice_df = df.iloc[start:end]

    # Serialise to plain Python — NaN → None
    rows: list[list[Any]] = []
    for _, row in slice_df.iterrows():
        serialised = []
        for v in row:
            if isinstance(v, float) and np.isnan(v):
                serialised.append(None)
            elif isinstance(v, (np.integer,)):
                serialised.append(int(v))
            elif isinstance(v, (np.floating,)):
                serialised.append(float(v))
            else:
                serialised.append(str(v) if pd.notna(v) else None)
        rows.append(serialised)

    return DatasetPreview(
        dataset_id=dataset_id,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        columns=list(df.columns),
        rows=rows,
    )


# ─────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────

async def delete_dataset(dataset_id: str, db: AsyncSession) -> str:
    """Delete DB record and raw file. Returns the deleted ID."""
    dataset = await _get_or_404(dataset_id, db)
    stored  = dataset.stored_filename

    await db.execute(delete(Dataset).where(Dataset.id == dataset_id))
    await db.commit()

    # Remove file from disk (best-effort — don't fail if already gone)
    file_path = settings.upload_dir_abs / stored
    file_path.unlink(missing_ok=True)

    return dataset_id


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

async def _get_or_404(dataset_id: str, db: AsyncSession) -> Dataset:
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise LookupError(f"Dataset '{dataset_id}' not found.")
    return dataset
