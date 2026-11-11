"""
Column role detector for electronic-tongue sensor datasets.

Detection heuristics
────────────────────
sample_id  — column name contains 'id', 'sample', 'no', 'num', 'index',
             or the column contains all-unique integer or string values
             AND has ≤ 1 unique value per row (i.e. likely an identifier).

category   — column name contains 'category', 'class', 'label', 'type',
             'group', 'dravya', 'herb', 'plant', 'species', 'variety',
             or the column is non-numeric with low cardinality (< 20% of rows).

sensor     — numeric column that is not classified as sample_id or category.
             The column must have at least one non-null numeric value.

ignored    — everything else (text columns that don't match category heuristics,
             all-null columns, duplicate columns, etc.).

These are SUGGESTIONS.  The user must confirm or correct them before any
analysis run.  No column is silently used as a feature.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

# Keyword patterns for heuristic matching (case-insensitive)
_ID_PATTERN  = re.compile(
    r"\b(id|sample|no|num|number|index|idx|sno|sr|serial|code|ref)\b",
    re.IGNORECASE,
)
_CAT_PATTERN = re.compile(
    r"\b(category|cat|class|label|type|group|dravya|herb|plant|"
    r"species|variety|family|genus|treatment|origin|provenance|source)\b",
    re.IGNORECASE,
)


def detect_column_roles(df: pd.DataFrame) -> dict[str, str]:
    """
    Returns a mapping {column_name: role} for every column in *df*.

    Roles: 'sensor' | 'sample_id' | 'category' | 'ignored'
    """
    roles: dict[str, str] = {}
    n_rows = len(df)

    for col in df.columns:
        series = df[col]
        col_lower = str(col).lower().strip()

        # ── 1. Always-ignore: all-null ────────────────────────
        if series.isna().all():
            roles[col] = "ignored"
            continue

        is_numeric = pd.api.types.is_numeric_dtype(series)
        n_unique   = series.nunique(dropna=True)

        # ── 2. Name-based sample_id detection ─────────────────
        if _ID_PATTERN.search(col_lower):
            roles[col] = "sample_id"
            continue

        # ── 3. Name-based category detection ──────────────────
        if _CAT_PATTERN.search(col_lower):
            roles[col] = "category"
            continue

        # ── 4. Value-based: unique identifier column ──────────
        # All-unique values that look like IDs (not pure floats)
        if n_unique == n_rows and not is_numeric:
            roles[col] = "sample_id"
            continue

        # ── 5. Value-based: low-cardinality non-numeric → category
        if not is_numeric and n_rows > 0:
            cardinality_ratio = n_unique / n_rows
            if cardinality_ratio < 0.20 and n_unique >= 2:
                roles[col] = "category"
                continue
            # High-cardinality non-numeric → ignored
            roles[col] = "ignored"
            continue

        # ── 6. Numeric with very few unique values → likely category
        if is_numeric and n_unique <= 5 and n_rows >= 10:
            # Could be a coded category (e.g. 1/2/3). Suggest category.
            roles[col] = "category"
            continue

        # ── 7. Numeric — suggest as sensor feature ────────────
        if is_numeric:
            roles[col] = "sensor"
            continue

        # ── 8. Fallback ───────────────────────────────────────
        roles[col] = "ignored"

    return roles


def build_column_info(df: pd.DataFrame, roles: dict[str, str]) -> list[dict[str, Any]]:
    """
    Build a per-column metadata list suitable for the ColumnInfo schema.
    """
    info = []
    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        # Gather up to 5 sample values, serialised to Python primitives
        samples: list[Any] = []
        for v in non_null.head(5):
            if isinstance(v, (np.integer,)):
                samples.append(int(v))
            elif isinstance(v, (np.floating,)):
                samples.append(None if np.isnan(v) else float(v))
            else:
                samples.append(str(v))

        info.append(
            {
                "name":           col,
                "detected_role":  roles[col],
                "dtype":          str(series.dtype),
                "missing_count":  int(series.isna().sum()),
                "unique_count":   int(series.nunique(dropna=True)),
                "sample_values":  samples,
            }
        )
    return info


def count_sensors(roles: dict[str, str]) -> int:
    return sum(1 for r in roles.values() if r == "sensor")
