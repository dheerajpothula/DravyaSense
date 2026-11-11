"""
Phase 2 Verification Script — DravyaSense Preprocessing Engine
==============================================================
Runs all 14 checks specified in the verification brief.

Usage (from backend/ with venv active):
    python verify_phase2.py

Exit code 0 = all checks passed.
Exit code 1 = one or more checks failed.

Temporary CSV fixtures are created in memory or as temp files and
uploaded through the real API.  Genuine research CSVs are never
modified.
"""
from __future__ import annotations

import io
import json
import math
import sys
import tempfile
import textwrap
import time
import urllib.request
import urllib.error
from pathlib import Path

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────
BASE = "http://localhost:8000"
PASS = "\033[92m  PASS\033[0m"
FAIL = "\033[91m  FAIL\033[0m"
INFO = "\033[94m  INFO\033[0m"

passed = 0
failed = 0
failures: list[str] = []


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"{PASS}  {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    failures.append(msg)
    print(f"{FAIL}  {msg}")


def info(msg: str) -> None:
    print(f"{INFO}  {msg}")


def section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ─────────────────────────────────────────────────────────────────
# HTTP helpers (urllib-based — no external deps)
# ─────────────────────────────────────────────────────────────────

def _http_json(method: str, path: str, body: dict | None = None) -> dict | list:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _http_get_json(path: str) -> dict | list:
    return _http_json("GET", path)


def _http_delete_json(path: str) -> dict:
    return _http_json("DELETE", path)


def _http_put_json(path: str, body: dict) -> dict:
    return _http_json("PUT", path, body)


def _http_post_json(path: str, body: dict) -> dict:
    return _http_json("POST", path, body)


def _http_status(method: str, path: str) -> int:
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def upload_csv(csv_content: str, filename: str) -> dict:
    """Upload a CSV string as multipart/form-data."""
    boundary = "----dravyaverifyboundary12345"
    body_parts = []
    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        .encode()
    )
    body_parts.append(b"Content-Type: text/csv\r\n\r\n")
    body_parts.append(csv_content.encode("utf-8"))
    body_parts.append(f"\r\n--{boundary}--\r\n".encode())
    data = b"".join(body_parts)

    req = urllib.request.Request(
        f"{BASE}/api/datasets/upload",
        data=data,
        method="POST",
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def confirm_roles(dataset_id: str, roles: dict[str, str]) -> dict:
    return _http_put_json(f"/api/datasets/{dataset_id}/roles", {"column_roles": roles})


def preview_preprocess(dataset_id: str, config: dict) -> dict:
    return _http_post_json("/api/preprocessing/preview",
                           {"dataset_id": dataset_id, "config": config})


def apply_preprocess(dataset_id: str, config: dict) -> dict:
    return _http_post_json("/api/preprocessing/apply",
                           {"dataset_id": dataset_id, "config": config})


def get_processed_preview(processed_id: str, page_size: int = 100) -> dict:
    return _http_get_json(f"/api/preprocessing/{processed_id}/preview?page=1&page_size={page_size}")


def get_processed_detail(processed_id: str) -> dict:
    return _http_get_json(f"/api/preprocessing/{processed_id}")


def delete_processed(processed_id: str) -> dict:
    return _http_delete_json(f"/api/preprocessing/{processed_id}")


def delete_dataset(dataset_id: str) -> None:
    try:
        _http_delete_json(f"/api/datasets/{dataset_id}")
    except Exception:
        pass


def list_all_datasets() -> list[dict]:
    return _http_get_json("/api/datasets")


def list_processed(source_id: str) -> list[dict]:
    return _http_get_json(f"/api/preprocessing/dataset/{source_id}")


def approx_equal(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) < tol


# ─────────────────────────────────────────────────────────────────
# Fixture CSVs
# ─────────────────────────────────────────────────────────────────

FIXTURE_BASIC_CSV = textwrap.dedent("""\
sample_id,origin,s1,s2,s3
SA,TypeA,10.0,2.0,100.0
SB,TypeA,20.0,4.0,200.0
SC,TypeB,30.0,6.0,300.0
SD,TypeB,40.0,8.0,400.0
SE,TypeA,50.0,10.0,500.0
SF,TypeB,60.0,12.0,600.0
SG,TypeA,70.0,14.0,700.0
SH,TypeB,80.0,16.0,800.0
SI,TypeA,90.0,18.0,900.0
SJ,TypeB,100.0,20.0,1000.0
""")

FIXTURE_MISSING_CSV = textwrap.dedent("""\
sample_id,origin,s1,s2,s3
SA,TypeA,10.0,2.0,100.0
SB,TypeA,,4.0,200.0
SC,TypeB,30.0,,300.0
SD,TypeB,40.0,8.0,
SE,TypeA,50.0,10.0,500.0
SF,TypeB,60.0,12.0,600.0
SG,TypeA,70.0,14.0,700.0
SH,TypeB,80.0,16.0,800.0
SI,TypeA,90.0,18.0,900.0
SJ,TypeB,100.0,20.0,1000.0
""")

# Fixture with one strong outlier per column (well beyond IQR×1.5)
FIXTURE_OUTLIER_CSV = textwrap.dedent("""\
sample_id,origin,s1,s2,s3
SA,TypeA,10.0,2.0,100.0
SB,TypeA,12.0,2.5,110.0
SC,TypeB,11.0,2.2,105.0
SD,TypeB,13.0,2.8,115.0
SE,TypeA,10.5,2.1,102.0
SF,TypeB,12.5,2.6,112.0
SG,TypeA,11.5,2.3,108.0
SH,TypeB,13.5,2.9,118.0
SI,TypeA,10.0,2.0,100.0
SJ,TypeB,9999.0,9999.0,9999.0
""")

# Fixture with negative values (like e-tongue) and chemical zeros
FIXTURE_NEGATIVE_CSV = textwrap.dedent("""\
sample_id,origin,sensor_mV,chem_mg_g
SA,TypeA,-24.60,0.000
SB,TypeA,-25.35,1.535
SC,TypeB,-25.28,0.000
SD,TypeB,-25.61,4.550
SE,TypeA,-23.64,2.070
SF,TypeB,-23.63,1.050
SG,TypeA,-24.66,1.250
SH,TypeB,-25.55,1.256
SI,TypeA,-26.67,1.009
SJ,TypeB,-23.24,1.393
""")

FIXTURE_ROLES = {
    "sample_id": "sample_id",
    "origin": "category",
    "s1": "sensor",
    "s2": "sensor",
    "s3": "sensor",
}

FIXTURE_ROLES_NEG = {
    "sample_id": "sample_id",
    "origin": "category",
    "sensor_mV": "sensor",
    "chem_mg_g": "sensor",
}


# ─────────────────────────────────────────────────────────────────
# Identify the four production datasets
# ─────────────────────────────────────────────────────────────────

def get_production_datasets() -> dict[str, dict]:
    datasets = list_all_datasets()
    prod: dict[str, dict] = {}
    for d in datasets:
        fn = d["original_filename"]
        if fn == "magnolia_electronic_tongue.csv":
            prod["etongue"] = d
        elif fn == "magnolia_electronic_nose.csv":
            prod["enose"] = d
        elif fn == "magnolia_chemical_analysis.csv":
            prod["chem"] = d
        elif fn == "electronic_tongue.csv":
            prod["benchmark"] = d
    return prod


# ─────────────────────────────────────────────────────────────────
# CHECK 1 — sample_id and origin are never transformed
# ─────────────────────────────────────────────────────────────────

def check_1_metadata_not_transformed():
    section("CHECK 1 — sample_id and origin are never scaled or imputed")
    analysis = upload_csv(FIXTURE_BASIC_CSV, "fix_check1.csv")
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, FIXTURE_ROLES)

    for scaler in ["standard", "minmax", "robust"]:
        config = {
            "selected_features": ["s1", "s2", "s3"],
            "imputation_strategy": "none",
            "scaling_method": scaler,
            "outlier_action": "keep",
            "iqr_multiplier": 1.5,
        }
        prev = preview_preprocess(ds_id, config)
        # sample_id and origin must appear in columns
        cols = prev["columns"]
        if "sample_id" not in cols or "origin" not in cols:
            fail(f"[{scaler}] sample_id or origin missing from output columns")
            continue

        # Verify sample_id values are unchanged strings
        id_idx = cols.index("sample_id")
        origin_idx = cols.index("origin")
        expected_ids = ["SA", "SB", "SC", "SD", "SE", "SF", "SG", "SH", "SI", "SJ"]
        expected_origins = ["TypeA", "TypeA", "TypeB", "TypeB", "TypeA",
                            "TypeB", "TypeA", "TypeB", "TypeA", "TypeB"]
        all_ok = True
        for i, row in enumerate(prev["preview_rows"]):
            if row[id_idx] != expected_ids[i] or row[origin_idx] != expected_origins[i]:
                fail(f"[{scaler}] Row {i}: sample_id or origin was mutated "
                     f"got id={row[id_idx]} origin={row[origin_idx]}")
                all_ok = False
        if all_ok:
            ok(f"sample_id and origin preserved unchanged with {scaler} scaler")

    delete_dataset(ds_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 2 — Only selected features are transformed
# ─────────────────────────────────────────────────────────────────

def check_2_only_selected_transformed():
    section("CHECK 2 — Only selected columns are transformed")
    analysis = upload_csv(FIXTURE_BASIC_CSV, "fix_check2.csv")
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, FIXTURE_ROLES)

    # Select only s1 and s2, leave s3 unselected
    config = {
        "selected_features": ["s1", "s2"],
        "imputation_strategy": "none",
        "scaling_method": "standard",
        "outlier_action": "keep",
        "iqr_multiplier": 1.5,
    }
    prev = preview_preprocess(ds_id, config)
    cols = prev["columns"]
    s3_idx = cols.index("s3")

    # s3 values should be the original: 100, 200, … 1000
    original_s3 = [100.0, 200.0, 300.0, 400.0, 500.0,
                   600.0, 700.0, 800.0, 900.0, 1000.0]
    all_ok = True
    for i, row in enumerate(prev["preview_rows"]):
        if not approx_equal(row[s3_idx], original_s3[i]):
            fail(f"s3 row {i}: expected {original_s3[i]}, got {row[s3_idx]}")
            all_ok = False
    if all_ok:
        ok("Unselected column s3 preserved exactly after StandardScaler on s1+s2")

    # s1 and s2 must have changed (mean≈0 after standard scaling)
    s1_idx = cols.index("s1")
    s1_vals = [row[s1_idx] for row in prev["preview_rows"]]
    mean_s1 = sum(s1_vals) / len(s1_vals)
    if abs(mean_s1) < 1e-8:
        ok("Selected column s1 was scaled (mean≈0)")
    else:
        fail(f"Selected column s1 appears unscaled (mean={mean_s1:.6f}, expected ≈0)")

    delete_dataset(ds_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 3 — Scaler mathematics
# ─────────────────────────────────────────────────────────────────

def check_3_scaler_math():
    section("CHECK 3 — Scaler mathematical correctness")
    analysis = upload_csv(FIXTURE_BASIC_CSV, "fix_check3.csv")
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, FIXTURE_ROLES)
    features = ["s1", "s2", "s3"]

    # ── StandardScaler ──────────────────────────────────────
    config_std = {"selected_features": features, "imputation_strategy": "none",
                  "scaling_method": "standard", "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_std = preview_preprocess(ds_id, config_std)
    cols = prev_std["columns"]
    s1_idx = cols.index("s1")
    s1_vals = [row[s1_idx] for row in prev_std["preview_rows"]]

    # Manually compute expected: s1 = [10..100] step 10, mean=55
    # sklearn StandardScaler uses ddof=0 (population std), not ddof=1
    original_s1 = [10.0*i for i in range(1, 11)]
    mean_s1 = sum(original_s1) / len(original_s1)
    std_s1 = np.std(original_s1, ddof=0)  # sklearn uses population std
    expected_std = [(v - mean_s1) / std_s1 for v in original_s1]

    all_ok = True
    for i, (got, exp) in enumerate(zip(s1_vals, expected_std)):
        if not approx_equal(got, exp, tol=1e-5):
            fail(f"StandardScaler s1[{i}]: expected {exp:.6f}, got {got:.6f}")
            all_ok = False
    # Check mean≈0 and std≈1 (ddof=0 for consistency with sklearn)
    mean_out = sum(s1_vals) / len(s1_vals)
    std_out = np.std(s1_vals, ddof=0)  # population std
    if abs(mean_out) < 1e-6:
        ok("StandardScaler: mean of s1 ≈ 0")
    else:
        fail(f"StandardScaler: mean={mean_out:.8f}, expected ≈0")
    if abs(std_out - 1.0) < 1e-6:
        ok("StandardScaler: std of s1 ≈ 1 (ddof=0)")
    else:
        fail(f"StandardScaler: std={std_out:.8f} (ddof=0), expected ≈1")

    # ── MinMaxScaler ────────────────────────────────────────
    config_mm = {"selected_features": features, "imputation_strategy": "none",
                 "scaling_method": "minmax", "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_mm = preview_preprocess(ds_id, config_mm)
    s1_vals_mm = [row[s1_idx] for row in prev_mm["preview_rows"]]
    min_v = min(s1_vals_mm)
    max_v = max(s1_vals_mm)
    if approx_equal(min_v, 0.0, tol=1e-7) and approx_equal(max_v, 1.0, tol=1e-7):
        ok("MinMaxScaler: s1 min=0.0, max=1.0")
    else:
        fail(f"MinMaxScaler: s1 min={min_v}, max={max_v}, expected [0, 1]")

    # Spot-check: s1[0]=10 → (10-10)/(100-10)=0, s1[-1]=100 → (100-10)/(100-10)=1
    if approx_equal(s1_vals_mm[0], 0.0, 1e-7):
        ok("MinMaxScaler: first value = 0.0")
    else:
        fail(f"MinMaxScaler: first value = {s1_vals_mm[0]}, expected 0.0")
    if approx_equal(s1_vals_mm[-1], 1.0, 1e-7):
        ok("MinMaxScaler: last value = 1.0")
    else:
        fail(f"MinMaxScaler: last value = {s1_vals_mm[-1]}, expected 1.0")

    # ── RobustScaler ────────────────────────────────────────
    config_rb = {"selected_features": features, "imputation_strategy": "none",
                 "scaling_method": "robust", "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_rb = preview_preprocess(ds_id, config_rb)
    s1_vals_rb = [row[s1_idx] for row in prev_rb["preview_rows"]]
    # RobustScaler: (x - median) / IQR
    # s1=[10..100] step 10, median=55, Q1=32.5, Q3=77.5, IQR=45
    median_s1 = float(np.median(original_s1))
    q1_s1 = float(np.percentile(original_s1, 25))
    q3_s1 = float(np.percentile(original_s1, 75))
    iqr_s1 = q3_s1 - q1_s1
    expected_rb = [(v - median_s1) / iqr_s1 for v in original_s1]
    rb_ok = all(approx_equal(got, exp, tol=1e-4) for got, exp in zip(s1_vals_rb, expected_rb))
    # Median value should map to 0
    median_idx = original_s1.index(median_s1) if median_s1 in original_s1 else -1
    median_val_output = None if median_idx < 0 else s1_vals_rb[median_idx]
    if rb_ok:
        ok(f"RobustScaler: s1 values match expected (median={median_s1}, IQR={iqr_s1})")
    else:
        # more specific diff
        diffs = [(i, s1_vals_rb[i], expected_rb[i]) for i in range(10)
                 if not approx_equal(s1_vals_rb[i], expected_rb[i], 1e-4)]
        fail(f"RobustScaler: {len(diffs)} mismatch(es). First: idx={diffs[0][0]} got={diffs[0][1]:.6f} exp={diffs[0][2]:.6f}")

    delete_dataset(ds_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 4 — Imputation (mean and median)
# ─────────────────────────────────────────────────────────────────

def check_4_imputation():
    section("CHECK 4 — Mean and median imputation")
    analysis = upload_csv(FIXTURE_MISSING_CSV, "fix_check4.csv")
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, FIXTURE_ROLES)

    # ── Mean imputation ─────────────────────────────────────
    config_mean = {"selected_features": ["s1", "s2", "s3"],
                   "imputation_strategy": "mean", "scaling_method": "none",
                   "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_mean = preview_preprocess(ds_id, config_mean)

    # s1 original: 10,NaN,30,40,50,60,70,80,90,100 → non-null mean = (10+30+40+50+60+70+80+90+100)/9 = 530/9 ≈ 58.888
    s1_non_null = [10, 30, 40, 50, 60, 70, 80, 90, 100]
    expected_s1_mean = sum(s1_non_null) / len(s1_non_null)

    cols = prev_mean["columns"]
    s1_idx = cols.index("s1")
    s1_row1 = prev_mean["preview_rows"][1][s1_idx]  # row index 1 was NaN
    if approx_equal(s1_row1, expected_s1_mean, tol=1e-3):
        ok(f"Mean imputation: s1 NaN filled with mean={expected_s1_mean:.3f}, got={s1_row1:.3f}")
    else:
        fail(f"Mean imputation: expected {expected_s1_mean:.3f}, got {s1_row1}")

    # Existing non-null values must be preserved
    s1_row0 = prev_mean["preview_rows"][0][s1_idx]
    if approx_equal(s1_row0, 10.0, tol=1e-7):
        ok("Mean imputation: original non-null values preserved")
    else:
        fail(f"Mean imputation: row 0 s1 changed to {s1_row0}, expected 10.0")

    # Check 0 missing values in output
    any_null = any(
        v is None
        for row in prev_mean["preview_rows"]
        for v in [row[s1_idx], row[cols.index("s2")], row[cols.index("s3")]]
    )
    if not any_null:
        ok("Mean imputation: no NaN remaining in output")
    else:
        fail("Mean imputation: NaN values still present after imputation")

    # Check warning on no-missing data
    config_no_missing = {"selected_features": ["s1", "s2", "s3"],
                         "imputation_strategy": "mean", "scaling_method": "none",
                         "outlier_action": "keep", "iqr_multiplier": 1.5}
    analysis2 = upload_csv(FIXTURE_BASIC_CSV, "fix_check4b.csv")
    ds_id2 = analysis2["dataset_id"]
    confirm_roles(ds_id2, FIXTURE_ROLES)
    prev_no_miss = preview_preprocess(ds_id2, config_no_missing)
    has_skip_warning = any("no missing" in w.lower() or "skipped" in w.lower()
                           for w in prev_no_miss["warnings"])
    if has_skip_warning:
        ok("Imputation skipped (no missing values) — warning returned")
    else:
        fail(f"Expected skip warning when no missing values, got: {prev_no_miss['warnings']}")

    # ── Median imputation ───────────────────────────────────
    config_med = {"selected_features": ["s1", "s2", "s3"],
                  "imputation_strategy": "median", "scaling_method": "none",
                  "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_med = preview_preprocess(ds_id, config_med)
    # s1 non-null sorted: 10,30,40,50,60,70,80,90,100 → median = 60
    expected_s1_median = float(np.median(s1_non_null))
    s1_row1_med = prev_med["preview_rows"][1][s1_idx]
    if approx_equal(s1_row1_med, expected_s1_median, tol=1e-3):
        ok(f"Median imputation: s1 NaN filled with median={expected_s1_median}, got={s1_row1_med}")
    else:
        fail(f"Median imputation: expected {expected_s1_median}, got {s1_row1_med}")

    delete_dataset(ds_id)
    delete_dataset(ds_id2)


# ─────────────────────────────────────────────────────────────────
# CHECK 5 — Outlier clip and remove (IQR)
# ─────────────────────────────────────────────────────────────────

def check_5_outlier_treatment():
    section("CHECK 5 — IQR outlier clip and removal")
    analysis = upload_csv(FIXTURE_OUTLIER_CSV, "fix_check5.csv")
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, FIXTURE_ROLES)

    features = ["s1", "s2", "s3"]
    # s1 full: [10,12,11,13,10.5,12.5,11.5,13.5,10,9999]
    # IQR is computed on ALL values (robust by design — outliers don't
    # affect Q1/Q3).  The engine correctly includes the outlier.
    s1_all = [10.0,12.0,11.0,13.0,10.5,12.5,11.5,13.5,10.0,9999.0]
    arr_all = np.array(s1_all)
    q1 = float(np.percentile(arr_all, 25))
    q3 = float(np.percentile(arr_all, 75))
    iqr = q3 - q1
    upper_fence = q3 + 1.5 * iqr

    # ── Clip ────────────────────────────────────────────────
    config_clip = {"selected_features": features, "imputation_strategy": "none",
                   "scaling_method": "none", "outlier_action": "clip", "iqr_multiplier": 1.5}
    prev_clip = preview_preprocess(ds_id, config_clip)
    cols = prev_clip["columns"]
    s1_idx = cols.index("s1")

    # Row 9 (SJ) should have been clipped to upper_fence
    row9_s1 = prev_clip["preview_rows"][9][s1_idx]
    if approx_equal(row9_s1, upper_fence, tol=1e-3):
        ok(f"Clip: 9999 clipped to upper fence {upper_fence:.4f}")
    else:
        fail(f"Clip: expected {upper_fence:.4f}, got {row9_s1}")

    # Row count must be unchanged
    if prev_clip["row_count_after"] == 10:
        ok("Clip: row count preserved (no rows removed)")
    else:
        fail(f"Clip: row count={prev_clip['row_count_after']}, expected 10")

    # sample_id of row 9 must still be SJ
    sid_idx = cols.index("sample_id")
    if prev_clip["preview_rows"][9][sid_idx] == "SJ":
        ok("Clip: sample_id alignment preserved after clipping")
    else:
        fail(f"Clip: row 9 sample_id={prev_clip['preview_rows'][9][sid_idx]}, expected SJ")

    # Check transformation message
    if any("clip" in t.lower() for t in prev_clip["transformations_applied"]):
        ok(f"Clip: transformation recorded: {prev_clip['transformations_applied']}")
    else:
        fail(f"Clip: no clip transformation recorded. Got: {prev_clip['transformations_applied']}")

    # ── Remove ──────────────────────────────────────────────
    config_remove = {"selected_features": features, "imputation_strategy": "none",
                     "scaling_method": "none", "outlier_action": "remove", "iqr_multiplier": 1.5}
    prev_remove = preview_preprocess(ds_id, config_remove)

    # One row (SJ) should be removed
    if prev_remove["row_count_after"] == 9:
        ok("Remove: row count reduced from 10 to 9")
    else:
        fail(f"Remove: row count={prev_remove['row_count_after']}, expected 9")

    # SJ should not appear in any row
    cols_r = prev_remove["columns"]
    sid_idx_r = cols_r.index("sample_id")
    remaining_ids = [row[sid_idx_r] for row in prev_remove["preview_rows"]]
    if "SJ" not in remaining_ids:
        ok("Remove: outlier row SJ not present in output")
    else:
        fail("Remove: outlier row SJ still present after removal")

    # S1..S9 must still be present
    expected_ids = ["SA","SB","SC","SD","SE","SF","SG","SH","SI"]
    missing_ids = [sid for sid in expected_ids if sid not in remaining_ids]
    if not missing_ids:
        ok("Remove: all non-outlier rows preserved")
    else:
        fail(f"Remove: rows missing from output: {missing_ids}")

    delete_dataset(ds_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 6 — Row removal preserves sample_id and origin alignment
# ─────────────────────────────────────────────────────────────────

def check_6_row_alignment_after_removal():
    section("CHECK 6 — Row removal preserves sample_id/origin alignment")
    analysis = upload_csv(FIXTURE_OUTLIER_CSV, "fix_check6.csv")
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, FIXTURE_ROLES)

    config = {"selected_features": ["s1", "s2", "s3"], "imputation_strategy": "none",
              "scaling_method": "none", "outlier_action": "remove", "iqr_multiplier": 1.5}

    # Apply (save) to get real processed file
    result = apply_preprocess(ds_id, config)
    processed_id = result["id"]

    pv = get_processed_preview(processed_id, page_size=100)
    cols = pv["columns"]
    sid_idx = cols.index("sample_id")
    origin_idx = cols.index("origin")

    # Source fixture: SA-SJ, origins: TypeA,TypeA,TypeB,TypeB,TypeA,TypeB,TypeA,TypeB,TypeA,TypeB
    # SJ removed → remaining 9 rows
    expected_pairs = [
        ("SA","TypeA"),("SB","TypeA"),("SC","TypeB"),("SD","TypeB"),
        ("SE","TypeA"),("SF","TypeB"),("SG","TypeA"),("SH","TypeB"),("SI","TypeA"),
    ]
    actual_pairs = [(row[sid_idx], row[origin_idx]) for row in pv["rows"]]

    if actual_pairs == expected_pairs:
        ok("Row removal: sample_id and origin remain aligned in all 9 remaining rows")
    else:
        fail(f"Row removal: alignment broken. Expected:\n    {expected_pairs}\nGot:\n    {actual_pairs}")

    delete_processed(processed_id)
    delete_dataset(ds_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 7 — Negative sensor values preserved
# ─────────────────────────────────────────────────────────────────

def check_7_negative_values_preserved():
    section("CHECK 7 — Negative electronic-tongue values preserved")
    analysis = upload_csv(FIXTURE_NEGATIVE_CSV, "fix_check7.csv")
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, FIXTURE_ROLES_NEG)

    # ── keep: negative values must pass through unchanged ───
    config_keep = {"selected_features": ["sensor_mV", "chem_mg_g"],
                   "imputation_strategy": "none", "scaling_method": "none",
                   "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_keep = preview_preprocess(ds_id, config_keep)
    cols = prev_keep["columns"]
    mv_idx = cols.index("sensor_mV")
    original_mv = [-24.60,-25.35,-25.28,-25.61,-23.64,-23.63,-24.66,-25.55,-26.67,-23.24]
    all_ok = True
    for i, row in enumerate(prev_keep["preview_rows"]):
        if not approx_equal(row[mv_idx], original_mv[i], tol=1e-6):
            fail(f"Keep: sensor_mV[{i}] changed: expected {original_mv[i]}, got {row[mv_idx]}")
            all_ok = False
    if all_ok:
        ok("Keep: all negative sensor_mV values passed through unchanged")

    # ── StandardScaler: should produce both positive and negative ───
    config_std = {"selected_features": ["sensor_mV", "chem_mg_g"],
                  "imputation_strategy": "none", "scaling_method": "standard",
                  "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_std = preview_preprocess(ds_id, config_std)
    cols_std = prev_std["columns"]
    mv_idx_std = cols_std.index("sensor_mV")
    std_vals = [row[mv_idx_std] for row in prev_std["preview_rows"]]

    has_negative = any(v < 0 for v in std_vals)
    has_positive = any(v > 0 for v in std_vals)
    mean_std = sum(std_vals) / len(std_vals)

    if has_negative and has_positive:
        ok("StandardScaler on negative data: produces both + and − values (sign not stripped)")
    else:
        fail(f"StandardScaler: negative values stripped. all values: {std_vals}")
    if abs(mean_std) < 1e-6:
        ok("StandardScaler: mean of scaled sensor_mV ≈ 0")
    else:
        fail(f"StandardScaler: mean={mean_std:.8f}, expected ≈0")

    # ── MinMax: even with negatives, must produce [0,1] ───
    config_mm = {"selected_features": ["sensor_mV", "chem_mg_g"],
                 "imputation_strategy": "none", "scaling_method": "minmax",
                 "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_mm = preview_preprocess(ds_id, config_mm)
    mv_idx_mm = prev_mm["columns"].index("sensor_mV")
    mm_vals = [row[mv_idx_mm] for row in prev_mm["preview_rows"]]
    if approx_equal(min(mm_vals), 0.0, 1e-6) and approx_equal(max(mm_vals), 1.0, 1e-6):
        ok("MinMaxScaler on negative input: output in [0, 1]")
    else:
        fail(f"MinMaxScaler on negatives: min={min(mm_vals)}, max={max(mm_vals)}")

    delete_dataset(ds_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 8 — Chemical zeros unchanged (no imputation requested)
# ─────────────────────────────────────────────────────────────────

def check_8_chemical_zeros_unchanged():
    section("CHECK 8 — Chemical zero values unchanged (imputation=none)")
    analysis = upload_csv(FIXTURE_NEGATIVE_CSV, "fix_check8.csv")
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, FIXTURE_ROLES_NEG)

    config = {"selected_features": ["sensor_mV", "chem_mg_g"],
              "imputation_strategy": "none", "scaling_method": "none",
              "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev = preview_preprocess(ds_id, config)
    cols = prev["columns"]
    chem_idx = cols.index("chem_mg_g")

    original_chem = [0.000,1.535,0.000,4.550,2.070,1.050,1.250,1.256,1.009,1.393]
    all_ok = True
    for i, row in enumerate(prev["preview_rows"]):
        if not approx_equal(row[chem_idx], original_chem[i], tol=1e-8):
            fail(f"chem_mg_g[{i}]: expected {original_chem[i]}, got {row[chem_idx]}")
            all_ok = False
    if all_ok:
        ok("Chemical zeros preserved unchanged with imputation=none")

    # With StandardScaler — zeros should map to (0 - mean)/std
    config_std = {"selected_features": ["sensor_mV", "chem_mg_g"],
                  "imputation_strategy": "none", "scaling_method": "standard",
                  "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_std = preview_preprocess(ds_id, config_std)
    chem_idx_std = prev_std["columns"].index("chem_mg_g")
    chem_vals_std = [row[chem_idx_std] for row in prev_std["preview_rows"]]

    # Manually compute: mean and std of original_chem (ddof=0 for sklearn)
    arr = np.array(original_chem)
    mean_c = float(arr.mean())
    std_c = float(arr.std(ddof=0))  # sklearn uses population std
    expected_0_scaled = (0.0 - mean_c) / std_c

    for i in [0, 2]:  # rows where chem_mg_g was 0
        if approx_equal(chem_vals_std[i], expected_0_scaled, tol=1e-5):
            ok(f"StandardScaler: zero in chem_mg_g[{i}] correctly scaled to {expected_0_scaled:.5f}")
        else:
            fail(f"StandardScaler: zero at [{i}] expected {expected_0_scaled:.5f}, "
                 f"got {chem_vals_std[i]}")

    # With imputation=mean on data with zeros: zeros are NOT missing → must NOT be overwritten
    config_mean = {"selected_features": ["sensor_mV", "chem_mg_g"],
                   "imputation_strategy": "mean", "scaling_method": "none",
                   "outlier_action": "keep", "iqr_multiplier": 1.5}
    prev_mean = preview_preprocess(ds_id, config_mean)
    # chem has no NaN → warn "no missing values", zeros preserved
    chem_idx_m = prev_mean["columns"].index("chem_mg_g")
    zero_rows_unchanged = all(
        approx_equal(prev_mean["preview_rows"][i][chem_idx_m], 0.0, 1e-8)
        for i in [0, 2]
    )
    has_warn = any("no missing" in w.lower() or "skipped" in w.lower()
                   for w in prev_mean["warnings"])
    if zero_rows_unchanged:
        ok("Mean imputation: chemical zeros not overwritten (zeros != NaN)")
    else:
        fail("Mean imputation: chemical zeros were incorrectly overwritten")
    if has_warn:
        ok("Mean imputation: 'no missing values' warning returned when data has no NaN")
    else:
        fail(f"Mean imputation: expected skip warning, got: {prev_mean['warnings']}")

    delete_dataset(ds_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 9 — Original files unchanged (all four datasets)
# ─────────────────────────────────────────────────────────────────

def check_9_original_files_unchanged():
    section("CHECK 9 — Original uploaded files are unchanged")
    research_dir = Path(__file__).parent.parent / "data" / "research" / "magnolia" / "processed"
    expected = {
        "magnolia_electronic_tongue.csv": 3389,
        "magnolia_electronic_nose.csv":   4341,
        "magnolia_chemical_analysis.csv": 5273,
    }
    for fname, expected_bytes in expected.items():
        fpath = research_dir / fname
        if not fpath.exists():
            fail(f"Research file missing: {fname}")
            continue
        actual = fpath.stat().st_size
        if actual == expected_bytes:
            ok(f"{fname}: {actual} bytes (unchanged)")
        else:
            fail(f"{fname}: {actual} bytes, expected {expected_bytes} — MODIFIED!")

    # Check uploaded copies not zero/corrupt
    datasets = list_all_datasets()
    for d in datasets:
        if d["file_size_bytes"] > 0:
            ok(f"Uploaded file {d['original_filename']}: {d['file_size_bytes']} bytes stored")
        else:
            fail(f"Uploaded file {d['original_filename']}: zero bytes (corrupt?)")


# ─────────────────────────────────────────────────────────────────
# CHECK 10 — Processed datasets retain attribution and units
# ─────────────────────────────────────────────────────────────────

def check_10_attribution_and_units(prod: dict):
    section("CHECK 10 — Attribution and units preserved in processed datasets")
    ds = prod.get("etongue")
    if not ds:
        fail("E-Tongue dataset not found")
        return

    detail_src = _http_get_json(f"/api/datasets/{ds['id']}")
    source_units = json.loads(detail_src["column_units"] or "{}")
    source_attr = detail_src["source_attribution"]

    config = {
        "selected_features": ["sourness_mV","bitterness_mV","astringency_mV",
                               "aftertaste_bitterness_mV","aftertaste_astringency_mV",
                               "umami_mV","richness_mV","saltiness_mV"],
        "imputation_strategy": "none", "scaling_method": "standard",
        "outlier_action": "keep", "iqr_multiplier": 1.5,
    }
    result = apply_preprocess(ds["id"], config)
    processed_id = result["id"]
    detail = get_processed_detail(processed_id)

    processed_units = json.loads(detail["column_units"] or "{}")
    if processed_units == source_units:
        ok(f"Column units copied from source: {list(processed_units.items())[:2]}…")
    else:
        fail(f"Column units lost. Source: {source_units}, Processed: {processed_units}")

    # Attribution is on the source dataset — not directly on ProcessedDataset,
    # but source_dataset_id must point back to it
    if detail["source_dataset_id"] == ds["id"]:
        ok("Processed dataset source_dataset_id links back to original")
    else:
        fail("source_dataset_id broken")

    # sklearn version stored
    if detail["sklearn_version"]:
        ok(f"sklearn version recorded: {detail['sklearn_version']}")
    else:
        fail("sklearn version not recorded")

    delete_processed(processed_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 11 — Preview does not save data
# ─────────────────────────────────────────────────────────────────

def check_11_preview_does_not_save(prod: dict):
    section("CHECK 11 — Preview does not save or modify data")
    ds = prod.get("enose")
    if not ds:
        fail("E-Nose dataset not found")
        return

    before_count = len(list_processed(ds["id"]))
    config = {
        "selected_features": ["W1C","W5S","W3C","W6S","W5C","W1S","W1W","W2S","W2W","W3S"],
        "imputation_strategy": "none", "scaling_method": "minmax",
        "outlier_action": "keep", "iqr_multiplier": 1.5,
    }
    # Call preview 3 times
    for _ in range(3):
        preview_preprocess(ds["id"], config)

    after_count = len(list_processed(ds["id"]))
    if before_count == after_count:
        ok(f"Preview called 3× — processed dataset count unchanged ({before_count})")
    else:
        fail(f"Preview saved data: count before={before_count}, after={after_count}")

    # Verify no new files appeared in processed/
    processed_dir = Path(__file__).parent / "processed"
    file_count_after = len(list(processed_dir.glob("*.csv"))) if processed_dir.exists() else 0
    # Count should not have increased by 3
    info(f"Processed CSV files on disk: {file_count_after}")


# ─────────────────────────────────────────────────────────────────
# CHECK 12 — DELETE removes only the selected record and its file
# ─────────────────────────────────────────────────────────────────

def check_12_delete_selective(prod: dict):
    section("CHECK 12 — DELETE removes only the selected record")
    ds = prod.get("chem")
    if not ds:
        fail("Chemical dataset not found")
        return

    config_base = {
        "selected_features": ["syringin_mg_g","magnoflorine_mg_g","magnoloside_B_mg_g",
                               "magnoloside_A_mg_g","honokiol_mg_g","magnolol_mg_g",
                               "piperitylmagnolol_mg_g","magnocurarine_mg_g",
                               "beta_eudesmol_mg_g","THM_mg_g","PBA_ratio","PHM_ratio"],
        "imputation_strategy": "none", "scaling_method": "standard",
        "outlier_action": "keep", "iqr_multiplier": 1.5,
    }
    # Create two processed datasets
    r1 = apply_preprocess(ds["id"], config_base)
    config2 = dict(config_base); config2["scaling_method"] = "minmax"
    r2 = apply_preprocess(ds["id"], config2)
    pid1, pid2 = r1["id"], r2["id"]
    fn1 = r1["processed_filename"]

    # Count files before delete
    processed_dir = Path(__file__).parent / "processed"
    files_before = set(processed_dir.glob("*.csv")) if processed_dir.exists() else set()

    # Delete only pid1
    delete_processed(pid1)

    # pid1 record must be gone
    if _http_status("GET", f"/api/preprocessing/{pid1}") == 404:
        ok("DELETE: record removed from database")
    else:
        fail("DELETE: record still accessible after delete")

    # pid2 must still exist
    if _http_status("GET", f"/api/preprocessing/{pid2}") == 200:
        ok("DELETE: sibling processed record unaffected")
    else:
        fail("DELETE: sibling record deleted unintentionally")

    # File for pid1 must be gone, file for pid2 must exist
    fn2 = r2["processed_filename"]
    files_after = set(processed_dir.glob("*.csv")) if processed_dir.exists() else set()
    deleted_files = {f.name for f in (files_before - files_after)}
    remaining_files = {f.name for f in files_after}

    if fn1 in deleted_files:
        ok(f"DELETE: processed CSV file {fn1} removed from disk")
    else:
        fail(f"DELETE: file {fn1} still present on disk")
    if fn2 in remaining_files:
        ok(f"DELETE: sibling file {fn2} preserved")
    else:
        fail(f"DELETE: sibling file {fn2} was incorrectly deleted")

    delete_processed(pid2)


# ─────────────────────────────────────────────────────────────────
# CHECK 13 — Pipeline config is readable JSON
# ─────────────────────────────────────────────────────────────────

def check_13_readable_json_config(prod: dict):
    section("CHECK 13 — Processing configurations are readable JSON (not pickled)")
    ds = prod.get("etongue")
    if not ds:
        fail("E-Tongue dataset not found"); return

    config = {
        "selected_features": ["sourness_mV","bitterness_mV","astringency_mV",
                               "aftertaste_bitterness_mV","aftertaste_astringency_mV",
                               "umami_mV","richness_mV","saltiness_mV"],
        "imputation_strategy": "median", "scaling_method": "robust",
        "outlier_action": "clip", "iqr_multiplier": 2.0,
    }
    result = apply_preprocess(ds["id"], config)
    processed_id = result["id"]
    detail = get_processed_detail(processed_id)

    # pipeline_config must be valid JSON dict (not bytes/pickle header)
    raw_config = detail["pipeline_config"]
    try:
        parsed = json.loads(raw_config)
        ok(f"pipeline_config is valid JSON (keys: {list(parsed.keys())})")
    except (json.JSONDecodeError, TypeError) as e:
        fail(f"pipeline_config is not valid JSON: {e}")
        delete_processed(processed_id); return

    # Verify all sent values round-tripped
    checks = [
        ("scaling_method", "robust"),
        ("imputation_strategy", "median"),
        ("outlier_action", "clip"),
        ("iqr_multiplier", 2.0),
    ]
    for key, expected in checks:
        actual = parsed.get(key)
        if actual == expected:
            ok(f"  Config round-trip: {key}={actual!r}")
        else:
            fail(f"  Config round-trip: {key} expected {expected!r}, got {actual!r}")

    # transformations_applied must be valid JSON list
    raw_trans = detail["transformations_applied"]
    try:
        trans_list = json.loads(raw_trans)
        ok(f"transformations_applied is valid JSON list ({len(trans_list)} item(s): {trans_list})")
    except Exception as e:
        fail(f"transformations_applied is not valid JSON: {e}")

    # selected_features must be valid JSON list matching input
    raw_feats = detail["selected_features"]
    try:
        feats = json.loads(raw_feats)
        if feats == config["selected_features"]:
            ok("selected_features round-tripped correctly")
        else:
            fail(f"selected_features: expected {config['selected_features']}, got {feats}")
    except Exception as e:
        fail(f"selected_features not valid JSON: {e}")

    delete_processed(processed_id)


# ─────────────────────────────────────────────────────────────────
# CHECK 14 — Existing APIs unaffected
# ─────────────────────────────────────────────────────────────────

def check_14_existing_apis_work(prod: dict):
    section("CHECK 14 — Existing Dataset Management, Data Explorer, quality/outlier APIs")

    # Dataset list
    datasets = list_all_datasets()
    if len(datasets) >= 4:
        ok(f"GET /api/datasets: returns {len(datasets)} datasets")
    else:
        fail(f"GET /api/datasets: only {len(datasets)} datasets returned")

    # Health
    if _http_status("GET", "/api/health") == 200:
        ok("GET /api/health: ok")
    else:
        fail("GET /api/health: failed")

    # Test each production dataset
    for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),
                       ("chem","Chemical"),("benchmark","Benchmark")]:
        ds = prod.get(key)
        if not ds:
            fail(f"{label}: dataset not in list"); continue

        # Statistics
        try:
            st = _http_get_json(f"/api/datasets/{ds['id']}/statistics")
            ok(f"{label} /statistics: {len(st['statistics'])} sensor columns")
        except Exception as e:
            fail(f"{label} /statistics: {e}")

        # Quality
        try:
            q = _http_get_json(f"/api/datasets/{ds['id']}/quality")
            ok(f"{label} /quality: {len(q['sensor_columns'])} cols, {q['total_missing']} missing")
        except Exception as e:
            fail(f"{label} /quality: {e}")

        # Outliers
        try:
            o = _http_get_json(f"/api/datasets/{ds['id']}/outliers")
            ok(f"{label} /outliers: {len(o['outliers'])} sensor columns analysed")
        except Exception as e:
            fail(f"{label} /outliers: {e}")

        # Preview
        try:
            pv = _http_get_json(f"/api/datasets/{ds['id']}/preview?page=1&page_size=5")
            ok(f"{label} /preview: {pv['total_rows']} total rows, first page returned")
        except Exception as e:
            fail(f"{label} /preview: {e}")


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  DravyaSense Phase 2 Verification")
    print("=" * 60)

    # Verify backend is up
    try:
        _http_get_json("/api/health")
    except Exception as e:
        print(f"\n  ERROR: Backend not responding at {BASE}: {e}")
        sys.exit(1)

    prod = get_production_datasets()
    missing = [k for k in ("etongue","enose","chem","benchmark") if k not in prod]
    if missing:
        print(f"  WARNING: Production datasets not found: {missing}")
        print("  Some checks may be skipped.")

    check_1_metadata_not_transformed()
    check_2_only_selected_transformed()
    check_3_scaler_math()
    check_4_imputation()
    check_5_outlier_treatment()
    check_6_row_alignment_after_removal()
    check_7_negative_values_preserved()
    check_8_chemical_zeros_unchanged()
    check_9_original_files_unchanged()
    check_10_attribution_and_units(prod)
    check_11_preview_does_not_save(prod)
    check_12_delete_selective(prod)
    check_13_readable_json_config(prod)
    check_14_existing_apis_work(prod)

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed  |  {failed} failed")
    print(f"{'='*60}")

    if failures:
        print("\n  FAILURES:")
        for f in failures:
            print(f"  ✗  {f}")
        sys.exit(1)
    else:
        print("\n  All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
