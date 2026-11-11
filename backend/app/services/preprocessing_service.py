"""
Preprocessing service — data quality analysis, outlier detection,
and preprocessing pipeline execution.

Phase 1:
  - analyze_quality()  — missing values, duplicates, invalid values
  - detect_outliers()  — IQR + Z-score per sensor column

Phase 2:
  - preview_preprocessing()    — apply config in memory, return preview
  - apply_preprocessing()       — apply config, save CSV, persist record
  - list_processed_datasets()   — list processed datasets for a source
  - get_processed_detail()       — retrieve a processed dataset record
  - get_processed_preview()      — paginated processed data
  - delete_processed()           — remove record + file

All operations target only sensor-role columns from the stored
column_roles.  sample_id and category columns are metadata only.
The original file on disk is never modified.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.dataset import Dataset
from app.models.processed_dataset import ProcessedDataset
from app.schemas.preprocessing import (
    ColumnQuality,
    ColumnStatsBeforeAfter,
    IQROutliers,
    OutlierReport,
    PreprocessingConfig,
    PreviewResponse,
    ProcessedDatasetDetail,
    ProcessedDatasetPreview,
    ProcessedDatasetSummary,
    QualityReport,
    SensorOutlierReport,
    ZScoreOutliers,
)

# Reuse file-parsing and DB-lookup helpers from the dataset service
from app.services.dataset_service import _get_or_404, _parse_file

settings = get_settings()


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

async def _load_sensor_data(
    dataset_id: str,
    db: AsyncSession,
) -> tuple[Dataset, pd.DataFrame, list[str], str | None]:
    """
    Load the stored file, parse it, and extract sensor + sample_id
    columns from the stored column_roles JSON.

    Returns:
        dataset, df, sensor_cols, sample_id_col
    """
    dataset   = await _get_or_404(dataset_id, db)
    file_path = settings.upload_dir_abs / dataset.stored_filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Raw file for dataset '{dataset_id}' not found on disk."
        )

    suffix = Path(dataset.stored_filename).suffix.lower()
    df = _parse_file(file_path.read_bytes(), suffix)

    roles = json.loads(dataset.column_roles)
    sensor_cols = [
        col for col, role in roles.items()
        if role == "sensor" and col in df.columns
    ]
    sample_id_col = next(
        (col for col, role in roles.items()
         if role == "sample_id" and col in df.columns),
        None,
    )

    return dataset, df, sensor_cols, sample_id_col


def _get_sample_id(
    df: pd.DataFrame,
    idx: Any,
    sample_id_col: str | None,
) -> str:
    """Return the sample identifier for a DataFrame row index."""
    if sample_id_col and sample_id_col in df.columns:
        val = df.loc[idx, sample_id_col]
        if pd.notna(val):
            return str(val)
    return f"row_{idx}"


# ─────────────────────────────────────────────────────────────────
# Data quality analysis
# ─────────────────────────────────────────────────────────────────

async def analyze_quality(
    dataset_id: str,
    db: AsyncSession,
) -> QualityReport:
    """
    Analyse data quality for all sensor columns:
    - Missing values (NaN)
    - Invalid values (inf / -inf, non-finite)
    - Duplicate rows (identical sensor readings across all sensors)
    """
    dataset, df, sensor_cols, sample_id_col = await _load_sensor_data(
        dataset_id, db,
    )

    columns_quality: list[ColumnQuality] = []
    total_missing = 0
    total_invalid = 0
    n_rows = len(df)

    for col in sensor_cols:
        series = df[col]
        n_missing = int(series.isna().sum())

        # Invalid = non-finite values that are not NaN (i.e. inf / -inf)
        if pd.api.types.is_numeric_dtype(series):
            n_invalid = int(np.isinf(series).sum())
        else:
            n_invalid = 0

        n_unique = int(series.nunique(dropna=True))

        columns_quality.append(ColumnQuality(
            column=col,
            missing_count=n_missing,
            missing_pct=round(n_missing / n_rows * 100, 2) if n_rows else 0.0,
            invalid_count=n_invalid,
            invalid_pct=round(n_invalid / n_rows * 100, 2) if n_rows else 0.0,
            unique_count=n_unique,
        ))

        total_missing += n_missing
        total_invalid += n_invalid

    # Duplicate rows across sensor columns
    duplicate_sample_ids: list[str] = []
    if sensor_cols and n_rows > 0:
        sensor_df = df[sensor_cols]
        dup_mask = sensor_df.duplicated(keep=False)
        duplicate_rows = int(dup_mask.sum())
        if duplicate_rows > 0:
            dup_indices = df.index[dup_mask].tolist()
            duplicate_sample_ids = [
                _get_sample_id(df, idx, sample_id_col)
                for idx in dup_indices
            ]
    else:
        duplicate_rows = 0

    return QualityReport(
        dataset_id=dataset_id,
        dataset_name=dataset.original_filename,
        row_count=n_rows,
        sensor_columns=sensor_cols,
        total_missing=total_missing,
        total_invalid=total_invalid,
        duplicate_rows=duplicate_rows,
        duplicate_sample_ids=duplicate_sample_ids,
        columns=columns_quality,
    )


# ─────────────────────────────────────────────────────────────────
# Outlier detection
# ─────────────────────────────────────────────────────────────────

async def detect_outliers(
    dataset_id: str,
    db: AsyncSession,
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
) -> OutlierReport:
    """
    Detect outliers in all sensor columns using IQR and Z-score methods.

    Only finite, non-null values are used to compute thresholds.
    Non-finite values (inf) are flagged as outliers when they exist.
    Zero-variance columns produce zero outliers for both methods.
    """
    dataset, df, sensor_cols, sample_id_col = await _load_sensor_data(
        dataset_id, db,
    )

    outlier_reports: list[SensorOutlierReport] = []

    for col in sensor_cols:
        series = df[col]
        non_null = series.dropna()

        # Filter to finite values for threshold computation
        if pd.api.types.is_numeric_dtype(series) and len(non_null) > 0:
            finite = non_null[np.isfinite(non_null)]
        else:
            finite = pd.Series([], dtype=series.dtype)

        # ── IQR ──────────────────────────────────────────────
        if len(finite) == 0:
            iqr_result = IQROutliers(
                q1=0.0, q3=0.0, iqr=0.0,
                lower_bound=0.0, upper_bound=0.0,
                outlier_count=0, outlier_sample_ids=[],
            )
        else:
            q1 = float(finite.quantile(0.25))
            q3 = float(finite.quantile(0.75))
            iqr_val = q3 - q1
            lower = q1 - iqr_multiplier * iqr_val
            upper = q3 + iqr_multiplier * iqr_val

            # Check all non-null values (including inf) against bounds
            if len(non_null) > 0:
                outlier_mask = (non_null < lower) | (non_null > upper)
                outlier_indices = non_null.index[outlier_mask].tolist()
                outlier_sids = [
                    _get_sample_id(df, idx, sample_id_col)
                    for idx in outlier_indices
                ]
            else:
                outlier_sids = []

            iqr_result = IQROutliers(
                q1=q1, q3=q3, iqr=iqr_val,
                lower_bound=lower, upper_bound=upper,
                outlier_count=len(outlier_sids),
                outlier_sample_ids=outlier_sids,
            )

        # ── Z-score ──────────────────────────────────────────
        if len(finite) == 0:
            zscore_result = ZScoreOutliers(
                mean=0.0, std=0.0, threshold=zscore_threshold,
                outlier_count=0, outlier_sample_ids=[],
            )
        else:
            mean = float(finite.mean())
            std = float(finite.std()) if len(finite) > 1 else 0.0

            if std == 0.0 or np.isnan(std):
                zscore_result = ZScoreOutliers(
                    mean=mean, std=std, threshold=zscore_threshold,
                    outlier_count=0, outlier_sample_ids=[],
                )
            else:
                # Z-scores for all non-null values (inf → z=inf → outlier)
                z_scores = (non_null - mean) / std
                outlier_mask = z_scores.abs() > zscore_threshold
                outlier_indices = non_null.index[outlier_mask].tolist()
                outlier_sids = [
                    _get_sample_id(df, idx, sample_id_col)
                    for idx in outlier_indices
                ]
                zscore_result = ZScoreOutliers(
                    mean=mean, std=std, threshold=zscore_threshold,
                    outlier_count=len(outlier_sids),
                    outlier_sample_ids=outlier_sids,
                )

        outlier_reports.append(SensorOutlierReport(
            column=col,
            iqr=iqr_result,
            zscore=zscore_result,
        ))

    return OutlierReport(
        dataset_id=dataset_id,
        dataset_name=dataset.original_filename,
        row_count=len(df),
        sensor_columns=sensor_cols,
        iqr_multiplier=iqr_multiplier,
        zscore_threshold=zscore_threshold,
        outliers=outlier_reports,
    )


# ═══════════════════════════════════════════════════════════════════
# Phase 2 — Preprocessing pipeline engine
# ═══════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
# Data loading helper
# ─────────────────────────────────────────────────────────────────

async def _load_data_for_preprocessing(
    dataset_id: str,
    db: AsyncSession,
) -> tuple[Dataset, pd.DataFrame, list[str], str | None, list[str]]:
    """
    Load the source dataset, parse its file, and extract all column
    groups from the stored column_roles JSON.

    Returns:
        dataset, df, sensor_cols, sample_id_col, category_cols
    """
    dataset   = await _get_or_404(dataset_id, db)
    file_path = settings.upload_dir_abs / dataset.stored_filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Raw file for dataset '{dataset_id}' not found on disk."
        )

    suffix = Path(dataset.stored_filename).suffix.lower()
    df = _parse_file(file_path.read_bytes(), suffix)

    roles = json.loads(dataset.column_roles)
    sensor_cols = [
        col for col, role in roles.items()
        if role == "sensor" and col in df.columns
    ]
    sample_id_col = next(
        (col for col, role in roles.items()
         if role == "sample_id" and col in df.columns),
        None,
    )
    category_cols = [
        col for col, role in roles.items()
        if role == "category" and col in df.columns
    ]

    return dataset, df, sensor_cols, sample_id_col, category_cols


# ─────────────────────────────────────────────────────────────────
# Core pipeline execution
# ─────────────────────────────────────────────────────────────────

def _execute_pipeline(
    df: pd.DataFrame,
    sensor_cols: list[str],
    config: PreprocessingConfig,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """
    Execute the preprocessing pipeline on a copy of the data.

    Order of operations:
      1. Imputation  (fill missing values)
      2. Outlier treatment (clip or remove — never automatic)
      3. Scaling     (standard / minmax / robust)

    Only `config.selected_features` (a subset of sensor_cols) are
    transformed.  Metadata columns (sample_id, category) are preserved
    untouched.

    Returns:
        processed_df, transformations_applied, warnings
    """
    result = df.copy()
    warnings: list[str] = []
    transformations: list[str] = []

    # Validate selected features are sensor columns
    selected = [c for c in config.selected_features if c in sensor_cols]
    if not selected:
        raise ValueError(
            "No valid sensor columns in selected_features. "
            "All selected columns must be assigned the 'sensor' role."
        )
    unknown = set(config.selected_features) - set(sensor_cols)
    if unknown:
        warnings.append(
            f"Columns not in sensor role and skipped: {', '.join(sorted(unknown))}"
        )

    sensor_data = result[selected].copy()

    # ── Step 1: Imputation ────────────────────────────────────
    if config.imputation_strategy != "none":
        n_missing = int(sensor_data.isna().sum().sum())
        if n_missing == 0:
            warnings.append(
                f"Imputation set to '{config.imputation_strategy}' but no "
                f"missing values found in selected columns — step skipped."
            )
        else:
            strategy = config.imputation_strategy
            for col in selected:
                if sensor_data[col].isna().any():
                    if strategy == "mean":
                        fill_val = float(sensor_data[col].mean())
                    elif strategy == "median":
                        fill_val = float(sensor_data[col].median())
                    else:
                        continue
                    sensor_data[col] = sensor_data[col].fillna(fill_val)
            transformations.append(
                f"Imputation ({strategy}): {n_missing} missing value(s) "
                f"filled across {len(selected)} column(s)"
            )

    # ── Step 2: Outlier treatment ────────────────────────────
    if config.outlier_action != "keep":
        action = config.outlier_action
        mult = config.iqr_multiplier

        if action == "clip":
            total_clipped = 0
            for col in selected:
                finite = sensor_data[col].dropna()
                if len(finite) < 4:
                    continue
                q1 = finite.quantile(0.25)
                q3 = finite.quantile(0.75)
                iqr = q3 - q1
                if iqr == 0:
                    continue  # zero IQR — cannot detect outliers
                lower = q1 - mult * iqr
                upper = q3 + mult * iqr
                mask = (sensor_data[col] < lower) | (sensor_data[col] > upper)
                total_clipped += int(mask.sum())
                sensor_data[col] = sensor_data[col].clip(lower, upper)
            if total_clipped > 0:
                transformations.append(
                    f"Outlier treatment (clip, IQR×{mult}): "
                    f"{total_clipped} value(s) clipped across {len(selected)} column(s)"
                )
            else:
                warnings.append(
                    f"Outlier clip configured (IQR×{mult}) but no outliers "
                    f"found — step skipped."
                )

        elif action == "remove":
            remove_mask = pd.Series(False, index=sensor_data.index)
            for col in selected:
                finite = sensor_data[col].dropna()
                if len(finite) < 4:
                    continue
                q1 = finite.quantile(0.25)
                q3 = finite.quantile(0.75)
                iqr = q3 - q1
                if iqr == 0:
                    continue
                lower = q1 - mult * iqr
                upper = q3 + mult * iqr
                col_mask = (sensor_data[col] < lower) | (sensor_data[col] > upper)
                remove_mask = remove_mask | col_mask
            n_removed = int(remove_mask.sum())
            if n_removed > 0:
                sensor_data = sensor_data[~remove_mask]
                result = result[~remove_mask]
                transformations.append(
                    f"Outlier treatment (remove, IQR×{mult}): "
                    f"{n_removed} row(s) removed"
                )
            else:
                warnings.append(
                    f"Outlier removal configured (IQR×{mult}) but no outliers "
                    f"found — step skipped."
                )

    # ── Step 3: Scaling ──────────────────────────────────────
    if config.scaling_method != "none":
        method = config.scaling_method
        # Identify zero-variance columns (cannot scale meaningfully)
        zero_var = [
            c for c in selected
            if sensor_data[c].std() == 0 or sensor_data[c].nunique() <= 1
        ]
        scale_cols = [c for c in selected if c not in zero_var]
        if zero_var:
            warnings.append(
                f"Zero-variance column(s) skipped during scaling: "
                f"{', '.join(zero_var)}"
            )
        if scale_cols:
            if method == "standard":
                scaler = StandardScaler()
            elif method == "minmax":
                scaler = MinMaxScaler()
            elif method == "robust":
                scaler = RobustScaler()
            else:
                scale_cols = []
            if scale_cols:
                sensor_data[scale_cols] = scaler.fit_transform(
                    sensor_data[scale_cols].values
                )
                transformations.append(
                    f"Scaling ({method}): applied to {len(scale_cols)} column(s)"
                )

    # Reassemble: put transformed sensor data back into the full DataFrame
    result.loc[:, selected] = sensor_data

    # ── Validation: no NaN or inf in sensor columns ──────────
    for col in selected:
        if result[col].isna().any():
            warnings.append(
                f"Column '{col}' still contains NaN values after preprocessing."
            )
        if np.isinf(result[col]).any():
            warnings.append(
                f"Column '{col}' contains infinity values after preprocessing."
            )

    return result, transformations, warnings


# ─────────────────────────────────────────────────────────────────
# Serialization helpers
# ─────────────────────────────────────────────────────────────────

def _serialize_value(v: Any) -> Any:
    """Convert a numpy/pandas scalar to a JSON-safe Python primitive."""
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, float):
        return None if np.isnan(v) else v
    if pd.isna(v):
        return None
    return str(v) if not isinstance(v, (int, float, str, bool)) else v


def _serialize_rows(df: pd.DataFrame, n: int) -> list[list[Any]]:
    """Serialize the first *n* rows of *df* to JSON-safe lists."""
    rows: list[list[Any]] = []
    for _, row in df.head(n).iterrows():
        rows.append([_serialize_value(v) for v in row])
    return rows


def _compute_column_stats(
    before: pd.DataFrame,
    after: pd.DataFrame,
    columns: list[str],
) -> list[ColumnStatsBeforeAfter]:
    """Compute before/after descriptive statistics for selected columns."""
    stats: list[ColumnStatsBeforeAfter] = []
    for col in columns:
        b = before[col].dropna()
        a = after[col].dropna()
        stats.append(ColumnStatsBeforeAfter(
            column=col,
            before_mean=float(b.mean()) if len(b) > 0 else None,
            before_std=float(b.std()) if len(b) > 1 else None,
            before_min=float(b.min()) if len(b) > 0 else None,
            before_max=float(b.max()) if len(b) > 0 else None,
            before_missing=int(before[col].isna().sum()),
            after_mean=float(a.mean()) if len(a) > 0 else None,
            after_std=float(a.std()) if len(a) > 1 else None,
            after_min=float(a.min()) if len(a) > 0 else None,
            after_max=float(a.max()) if len(a) > 0 else None,
            after_missing=int(after[col].isna().sum()),
        ))
    return stats


# ─────────────────────────────────────────────────────────────────
# Preview (no save)
# ─────────────────────────────────────────────────────────────────

async def preview_preprocessing(
    dataset_id: str,
    config: PreprocessingConfig,
    db: AsyncSession,
) -> PreviewResponse:
    """
    Apply the preprocessing config to the source data in memory and
    return a preview.  Nothing is saved to disk or the database.
    """
    dataset, df, sensor_cols, sample_id_col, category_cols = \
        await _load_data_for_preprocessing(dataset_id, db)

    # Validate selected features
    selected = [c for c in config.selected_features if c in sensor_cols]
    if not selected:
        raise ValueError(
            "No valid sensor columns selected. "
            "selected_features must contain at least one sensor column."
        )

    before_rows = len(df)
    processed, transformations, warnings = _execute_pipeline(
        df, sensor_cols, config,
    )
    after_rows = len(processed)

    preview_rows = _serialize_rows(processed, 10)
    column_stats = _compute_column_stats(df, processed, selected)

    # ── Compute processed column units for preview ────────────
    _SCALING_UNIT: dict[str, str] = {
        "standard": "z-score",
        "minmax":   "[0,1]",
        "robust":   "robust-scaled",
    }
    source_units: dict[str, str] = json.loads(dataset.column_units or "{}")
    scaling_unit = _SCALING_UNIT.get(config.scaling_method)
    if scaling_unit is not None:
        processed_column_units = dict(source_units)
        for col in selected:
            processed_column_units[col] = scaling_unit
    else:
        processed_column_units = dict(source_units)

    return PreviewResponse(
        dataset_id=dataset_id,
        source_filename=dataset.original_filename,
        row_count_before=before_rows,
        row_count_after=after_rows,
        columns=list(processed.columns),
        selected_features=selected,
        sample_id_column=sample_id_col,
        category_columns=category_cols,
        preview_rows=preview_rows,
        transformations_applied=transformations,
        warnings=warnings,
        column_stats=column_stats,
        processed_column_units=processed_column_units,
    )


# ─────────────────────────────────────────────────────────────────
# Apply (save processed data + persist record)
# ─────────────────────────────────────────────────────────────────

async def apply_preprocessing(
    dataset_id: str,
    config: PreprocessingConfig,
    db: AsyncSession,
) -> ProcessedDatasetDetail:
    """
    Apply the preprocessing config, save the processed data as a CSV
    file, and persist a ProcessedDataset record to the database.
    """
    dataset, df, sensor_cols, sample_id_col, category_cols = \
        await _load_data_for_preprocessing(dataset_id, db)

    # Validate selected features
    selected = [c for c in config.selected_features if c in sensor_cols]
    if not selected:
        raise ValueError(
            "No valid sensor columns selected. "
            "selected_features must contain at least one sensor column."
        )

    processed, transformations, warnings = _execute_pipeline(
        df, sensor_cols, config,
    )

    # ── Save processed data as CSV ────────────────────────────
    processed_dir = settings.processed_dir_abs
    processed_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}.csv"
    file_path = processed_dir / stored_name

    csv_bytes = processed.to_csv(index=False, encoding="utf-8").encode("utf-8")
    file_path.write_bytes(csv_bytes)

    # Count missing values in the processed sensor columns
    n_missing = int(processed[selected].isna().sum().sum())

    # ── Compute processed column units ───────────────────────
    # Selected features that were scaled receive a new unit label
    # that reflects the transformation applied.  Unselected sensor
    # columns and all metadata columns keep their original units.
    _SCALING_UNIT: dict[str, str] = {
        "standard": "z-score",
        "minmax":   "[0,1]",
        "robust":   "robust-scaled",
    }
    source_units: dict[str, str] = json.loads(dataset.column_units or "{}")
    scaling_unit = _SCALING_UNIT.get(config.scaling_method)

    if scaling_unit is not None:
        # Start from a copy of the source units, then overwrite for
        # every selected feature that was actually scaled.
        processed_units = dict(source_units)
        for col in selected:
            processed_units[col] = scaling_unit
        processed_column_units = json.dumps(processed_units)
    else:
        # No scaling — preserve source units verbatim
        processed_column_units = dataset.column_units

    # ── Build pipeline config JSON ───────────────────────────
    pipeline_config = {
        "selected_features": selected,
        "imputation_strategy": config.imputation_strategy,
        "scaling_method": config.scaling_method,
        "outlier_action": config.outlier_action,
        "iqr_multiplier": config.iqr_multiplier,
        "warnings": warnings,
    }

    record = ProcessedDataset(
        source_dataset_id=dataset_id,
        source_filename=dataset.original_filename,
        processed_filename=stored_name,
        file_size_bytes=len(csv_bytes),
        row_count=len(processed),
        column_count=len(processed.columns),
        sensor_column_count=len(selected),
        missing_value_count=n_missing,
        selected_features=json.dumps(selected),
        pipeline_config=json.dumps(pipeline_config),
        transformations_applied=json.dumps(transformations),
        column_units=processed_column_units,
        sklearn_version=sklearn.__version__,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    detail = ProcessedDatasetDetail.model_validate(record)
    # Populate derived scaler_type so the response is consistent
    detail.scaler_type = config.scaling_method
    return detail


# ─────────────────────────────────────────────────────────────────
# Processed dataset CRUD
# ─────────────────────────────────────────────────────────────────

async def _get_processed_or_404(
    processed_id: str,
    db: AsyncSession,
) -> ProcessedDataset:
    result = await db.execute(
        select(ProcessedDataset).where(ProcessedDataset.id == processed_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise LookupError(f"Processed dataset '{processed_id}' not found.")
    return record


async def list_processed_datasets(
    source_dataset_id: str,
    db: AsyncSession,
) -> list[ProcessedDatasetSummary]:
    """List all processed datasets derived from a given source dataset."""
    result = await db.execute(
        select(ProcessedDataset)
        .where(ProcessedDataset.source_dataset_id == source_dataset_id)
        .order_by(ProcessedDataset.created_at.desc())
    )
    summaries: list[ProcessedDatasetSummary] = []
    for r in result.scalars().all():
        summary = ProcessedDatasetSummary.model_validate(r)
        # Extract scaling_method from the pipeline_config JSON blob so
        # the listing carries enough info to disambiguate duplicate
        # runs of the same source dataset in the dropdown.
        try:
            cfg = json.loads(r.pipeline_config) if r.pipeline_config else {}
            summary.scaler_type = cfg.get("scaling_method")
        except (json.JSONDecodeError, TypeError):
            summary.scaler_type = None
        summaries.append(summary)
    return summaries


async def get_processed_detail(
    processed_id: str,
    db: AsyncSession,
) -> ProcessedDatasetDetail:
    record = await _get_processed_or_404(processed_id, db)
    detail = ProcessedDatasetDetail.model_validate(record)
    # Populate derived scaler_type from pipeline_config JSON
    try:
        cfg = json.loads(record.pipeline_config) if record.pipeline_config else {}
        detail.scaler_type = cfg.get("scaling_method")
    except (json.JSONDecodeError, TypeError):
        detail.scaler_type = None
    return detail


async def get_processed_preview(
    processed_id: str,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> ProcessedDatasetPreview:
    """Return a paginated slice of the processed CSV file."""
    record = await _get_processed_or_404(processed_id, db)
    file_path = settings.processed_dir_abs / record.processed_filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Processed file for '{processed_id}' not found on disk."
        )

    df = pd.read_csv(file_path, encoding="utf-8")

    total_rows = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    slice_df = df.iloc[start:end]

    rows = [_serialize_row(row) for _, row in slice_df.iterrows()]

    return ProcessedDatasetPreview(
        processed_id=processed_id,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        columns=list(df.columns),
        rows=rows,
    )


def _serialize_row(row: pd.Series) -> list[Any]:
    """Serialize a pandas Series (row) to JSON-safe Python primitives."""
    return [_serialize_value(v) for v in row]


async def delete_processed(
    processed_id: str,
    db: AsyncSession,
) -> str:
    """Delete a processed dataset record and its file from disk."""
    record = await _get_processed_or_404(processed_id, db)
    stored = record.processed_filename

    await db.execute(
        delete(ProcessedDataset).where(ProcessedDataset.id == processed_id)
    )
    await db.commit()

    file_path = settings.processed_dir_abs / stored
    file_path.unlink(missing_ok=True)

    return processed_id
