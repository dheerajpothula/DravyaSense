"""
Shared feature-loading utilities for dimensionality-reduction services.

Both the PCA service and the t-SNE service load data through these
helpers.  Keeping them in one place ensures that the metadata-isolation
guarantee — sample_id and category columns NEVER enter the numerical
feature matrix — is enforced in exactly one location.

Public surface
──────────────
  FeatureBundle          — data class carrying feature matrix + metadata
  load_raw_dataset()     — load from a Dataset (raw upload)
  load_processed_dataset() — load from a ProcessedDataset (preprocessed CSV)

Design rules
────────────
• sample_id and category columns are extracted before the feature matrix
  is built and are NEVER included in it.
• Processed datasets are loaded as-is: no additional scaling is applied
  here.  The caller (PCA / t-SNE service) receives data exactly as it
  came out of Preprocessing Studio.
• Zero-variance columns are dropped with a warning rather than crashing.
• NaN and infinity values raise ValueError with a clear message so the
  API layer can return an informative HTTP 422.
• Nothing in this module touches sklearn.  It is pure data plumbing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.dataset import Dataset
from app.models.processed_dataset import ProcessedDataset
from app.services.dataset_service import _get_or_404, _parse_file
from app.services.preprocessing_service import _get_processed_or_404

import json

settings = get_settings()


# ─────────────────────────────────────────────────────────────────
# Feature bundle
# ─────────────────────────────────────────────────────────────────

@dataclass
class FeatureBundle:
    """
    All data needed by a dimensionality-reduction algorithm, after
    metadata has been separated from the numerical feature matrix.

    Attributes
    ----------
    feature_matrix :
        Validated, finite NumPy array of shape (n_samples, n_features).
        Contains ONLY numerical sensor columns — no sample_id or category.
    feature_columns :
        Ordered column names corresponding to the feature matrix columns.
    sample_ids :
        Per-row identifier strings used for plot tooltips and CSV export.
        Derived from the sample_id column if present; otherwise "row_N".
    category_labels :
        Per-row category strings for optional colouring.  Empty list when
        no category column exists.
    category_column :
        Name of the category column used, or None.
    source_filename :
        Original filename of the source dataset (for display / storage).
    preprocessing_summary :
        Human-readable description of upstream preprocessing steps, or
        None if no preprocessing was applied (raw dataset).
    dropped_features :
        Column names excluded due to zero variance.  May be empty.
    warnings :
        Accumulated non-fatal diagnostic messages.
    """
    feature_matrix:        np.ndarray
    feature_columns:       list[str]
    sample_ids:            list[str]
    category_labels:       list[str]
    category_column:       str | None
    source_filename:       str
    preprocessing_summary: str | None
    dropped_features:      list[str] = field(default_factory=list)
    warnings:              list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Public loaders
# ─────────────────────────────────────────────────────────────────

async def load_raw_dataset(
    dataset_id: str,
    feature_columns_override: list[str] | None,
    db: AsyncSession,
) -> FeatureBundle:
    """
    Load a raw Dataset record, extract its feature matrix and metadata.

    Parameters
    ----------
    dataset_id :
        UUID of the Dataset record.
    feature_columns_override :
        If provided, only these columns enter the feature matrix
        (intersected with the sensor-role columns from column_roles).
        If None, all sensor-role columns are used.
    db :
        Async SQLAlchemy session.

    Raises
    ------
    LookupError
        If the Dataset record does not exist.
    FileNotFoundError
        If the uploaded file is missing from disk.
    ValueError
        If the feature matrix contains NaN, infinity, or has no valid
        numeric columns.
    """
    dataset = await _get_or_404(dataset_id, db)
    file_path = settings.upload_dir_abs / dataset.stored_filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Raw file for dataset '{dataset_id}' not found on disk."
        )

    suffix = Path(dataset.stored_filename).suffix.lower()
    df = _parse_file(file_path.read_bytes(), suffix)

    roles         = json.loads(dataset.column_roles)
    sensor_cols   = [c for c, r in roles.items() if r == "sensor"    and c in df.columns]
    sample_id_col = next((c for c, r in roles.items() if r == "sample_id" and c in df.columns), None)
    category_cols = [c for c, r in roles.items() if r == "category"  and c in df.columns]

    feature_cols = _resolve_features(
        sensor_cols, feature_columns_override, sample_id_col, category_cols
    )
    if not feature_cols:
        raise ValueError(
            "No valid sensor columns available. "
            "Assign at least one column the 'sensor' role."
        )

    sample_ids, category_labels, category_column = _extract_metadata(
        df, sample_id_col, category_cols
    )

    preprocessing_summary = (
        "Raw dataset — no scaling applied. "
        "Algorithm centres features but does not standardise their scales."
    )

    return _build_bundle(
        df=df,
        feature_cols=feature_cols,
        sample_ids=sample_ids,
        category_labels=category_labels,
        category_column=category_column,
        source_filename=dataset.original_filename,
        preprocessing_summary=preprocessing_summary,
    )


async def load_processed_dataset(
    processed_id: str,
    feature_columns_override: list[str] | None,
    db: AsyncSession,
) -> FeatureBundle:
    """
    Load a ProcessedDataset record, extract its feature matrix and metadata.

    The processed CSV is loaded as-is — no scaling or transformation is
    applied here.  The caller receives data exactly as it was saved by
    Preprocessing Studio.

    Parameters
    ----------
    processed_id :
        UUID of the ProcessedDataset record.
    feature_columns_override :
        If provided, only these columns enter the feature matrix
        (intersected with the selected_features list from the record).
        If None, all selected_features columns are used.
    db :
        Async SQLAlchemy session.

    Raises
    ------
    LookupError
        If the ProcessedDataset record does not exist.
    FileNotFoundError
        If the processed CSV file is missing from disk.
    ValueError
        If the feature matrix contains NaN, infinity, or has no valid
        numeric columns.
    """
    record = await _get_processed_or_404(processed_id, db)
    file_path = settings.processed_dir_abs / record.processed_filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Processed file for '{processed_id}' not found on disk."
        )

    df = pd.read_csv(file_path, encoding="utf-8")

    selected_features = json.loads(record.selected_features)

    # Locate sample_id and category columns from the SOURCE dataset's roles
    source_dataset = await _get_or_404(record.source_dataset_id, db)
    source_roles   = json.loads(source_dataset.column_roles)

    sample_id_col = next(
        (c for c, r in source_roles.items() if r == "sample_id" and c in df.columns),
        None,
    )
    category_cols = [
        c for c, r in source_roles.items()
        if r == "category" and c in df.columns
    ]

    feature_cols = _resolve_features(
        selected_features, feature_columns_override, sample_id_col, category_cols
    )
    if not feature_cols:
        raise ValueError(
            "No valid feature columns available from the processed dataset."
        )

    # Build a human-readable preprocessing summary from pipeline_config
    preprocessing_summary = _summarise_pipeline(record.pipeline_config)

    sample_ids, category_labels, category_column = _extract_metadata(
        df, sample_id_col, category_cols
    )

    return _build_bundle(
        df=df,
        feature_cols=feature_cols,
        sample_ids=sample_ids,
        category_labels=category_labels,
        category_column=category_column,
        source_filename=record.source_filename,
        preprocessing_summary=preprocessing_summary,
    )


# ─────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────

def _resolve_features(
    available: list[str],
    override: list[str] | None,
    sample_id_col: str | None,
    category_cols: list[str],
) -> list[str]:
    """
    Return the ordered list of column names to enter the feature matrix.

    If `override` is given, it is intersected with `available` (preserving
    the override ordering).  sample_id and category columns are always
    excluded, even if explicitly requested.
    """
    excluded = set(filter(None, [sample_id_col] + list(category_cols)))
    base = [c for c in available if c not in excluded]

    if override is None:
        return base

    override_clean = [c for c in override if c in base]
    return override_clean if override_clean else base


def _extract_metadata(
    df: pd.DataFrame,
    sample_id_col: str | None,
    category_cols: list[str],
) -> tuple[list[str], list[str], str | None]:
    """
    Extract per-row sample IDs and category labels as plain Python lists.

    Returns
    -------
    sample_ids :
        String identifier for each row.  Falls back to "row_N" when no
        sample_id column is present or the value is missing.
    category_labels :
        Values from the first category column, or an empty list.
    category_column :
        Name of the category column used, or None.
    """
    n = len(df)

    if sample_id_col and sample_id_col in df.columns:
        sample_ids: list[str] = [
            str(v) if pd.notna(v) else f"row_{i}"
            for i, v in enumerate(df[sample_id_col])
        ]
    else:
        sample_ids = [f"row_{i}" for i in range(n)]

    if category_cols:
        cat_col = category_cols[0]
        category_labels: list[str] = [
            str(v) if pd.notna(v) else "" for v in df[cat_col]
        ]
        category_column: str | None = cat_col
    else:
        category_labels = []
        category_column = None

    return sample_ids, category_labels, category_column


def _build_bundle(
    df: pd.DataFrame,
    feature_cols: list[str],
    sample_ids: list[str],
    category_labels: list[str],
    category_column: str | None,
    source_filename: str,
    preprocessing_summary: str | None,
) -> FeatureBundle:
    """
    Extract the feature matrix from `df`, validate it, drop zero-variance
    columns, and return a FeatureBundle.

    Raises ValueError on NaN or infinity.  Emits warnings for non-numeric
    or zero-variance columns.
    """
    warnings_out: list[str] = []
    dropped: list[str] = []

    # ── 1. Keep only numeric columns that exist in df ────────
    valid_cols = [
        c for c in feature_cols
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
    ]
    non_numeric = [c for c in feature_cols if c not in valid_cols]
    if non_numeric:
        warnings_out.append(
            f"Non-numeric columns excluded from feature matrix: "
            f"{', '.join(non_numeric)}"
        )

    if not valid_cols:
        raise ValueError(
            "No numeric feature columns remain after filtering. "
            "Ensure sensor columns contain numeric data."
        )

    X = df[valid_cols].values.astype(float)

    # ── 2. Reject NaN ────────────────────────────────────────
    nan_counts = np.isnan(X).sum(axis=0)
    if nan_counts.any():
        nan_cols = [valid_cols[i] for i, has in enumerate(nan_counts > 0) if has]
        raise ValueError(
            f"Feature matrix contains NaN values in: {', '.join(nan_cols)}. "
            f"Run imputation in Preprocessing Studio before analysis."
        )

    # ── 3. Reject infinity ───────────────────────────────────
    inf_counts = np.isinf(X).sum(axis=0)
    if inf_counts.any():
        inf_cols = [valid_cols[i] for i, has in enumerate(inf_counts > 0) if has]
        raise ValueError(
            f"Feature matrix contains infinity values in: {', '.join(inf_cols)}. "
            f"Inspect data quality before analysis."
        )

    # ── 4. Drop zero-variance columns ────────────────────────
    variances = np.var(X, axis=0)
    zero_var_mask = variances == 0
    if zero_var_mask.any():
        dropped = [valid_cols[i] for i, is_zero in enumerate(zero_var_mask) if is_zero]
        warnings_out.append(
            f"Zero-variance column(s) excluded (constant values): "
            f"{', '.join(dropped)}"
        )
        keep = ~zero_var_mask
        X = X[:, keep]
        valid_cols = [c for c, k in zip(valid_cols, keep) if k]

    if X.shape[1] == 0:
        raise ValueError(
            "All feature columns have zero variance. "
            "Analysis cannot be computed on constant data."
        )

    return FeatureBundle(
        feature_matrix=X,
        feature_columns=valid_cols,
        sample_ids=sample_ids,
        category_labels=category_labels,
        category_column=category_column,
        source_filename=source_filename,
        preprocessing_summary=preprocessing_summary,
        dropped_features=dropped,
        warnings=warnings_out,
    )


def _summarise_pipeline(pipeline_config_json: str) -> str:
    """
    Build a human-readable preprocessing summary from a pipeline_config
    JSON string (as stored in ProcessedDataset.pipeline_config).
    """
    try:
        cfg = json.loads(pipeline_config_json) if pipeline_config_json else {}
        parts: list[str] = []
        scaling = cfg.get("scaling_method", "none")
        if scaling and scaling != "none":
            parts.append(f"Scaling: {scaling}")
        imputation = cfg.get("imputation_strategy", "none")
        if imputation and imputation != "none":
            parts.append(f"Imputation: {imputation}")
        outlier = cfg.get("outlier_action", "keep")
        if outlier and outlier != "keep":
            parts.append(
                f"Outlier treatment: {outlier} "
                f"(IQR\u00d7{cfg.get('iqr_multiplier', 1.5)})"
            )
        summary = "; ".join(parts) if parts else "No scaling applied"
        if scaling == "none":
            summary += (
                " — algorithm centres features but does not standardise their scales."
            )
        return summary
    except Exception:
        return "Processed dataset (configuration unavailable)"
