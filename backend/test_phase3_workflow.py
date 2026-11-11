"""
Phase 3 workflow test — validates the full frontend→backend contract
exercised by the Preprocessing Studio UI.

Tests all four datasets through:
  1.  Dataset listing (selector data)
  2.  Dataset detail + statistics (meta strip, feature list)
  3.  Preview preprocessing — all four datasets, distinct configs
  4.  Apply preprocessing (save)
  5.  List processed history
  6.  Get processed detail
  7.  Get processed preview (paginated)
  8.  Original research files unchanged
  9.  Modality separation
  10. Delete processed dataset without affecting source

Schema-aware metadata checks:
  - Magnolia datasets (e-tongue, e-nose, chemical): sample_id column +
    origin category column present.
  - Pork benchmark: sample_id column present; no category columns (the
    benchmark has no origin or herbal-label column — this is correct).

$PID naming note:
  Python variable names are independent of PowerShell reserved variables.
  All processed-dataset IDs are stored in the dict `saved` to avoid any
  shell-level naming conflicts when the script output is parsed.

Exit 0 = all pass. Exit 1 = one or more failures.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://localhost:8000"
GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

passed: int = 0
failed: int = 0
failures: list[str] = []


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"{GREEN} PASS{RESET}  {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    failures.append(msg)
    print(f"{RED} FAIL{RESET}  {msg}")


def section(title: str) -> None:
    print(f"\n── {title} ──")


# ── HTTP helpers ──────────────────────────────────────────────────

def http_get(path: str) -> dict | list:
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.loads(r.read())


def http_post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def http_delete(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", method="DELETE")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def http_status(path: str) -> int:
    try:
        req = urllib.request.Request(f"{BASE}{path}", method="GET")
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


# ── Dataset schema definitions ────────────────────────────────────
# Defines what each dataset's column roles should look like after
# upload and role confirmation.  Used to drive schema-aware checks.

DATASET_SCHEMAS: dict[str, dict] = {
    "etongue": {
        "filename":          "magnolia_electronic_tongue.csv",
        "sensor_count":      8,
        "has_sample_id":     True,
        "category_columns":  ["origin"],   # Magnolia provenance label
        "measurement_type":  "electronic_tongue",
        "has_attribution":   True,
        "has_units":         True,
    },
    "enose": {
        "filename":          "magnolia_electronic_nose.csv",
        "sensor_count":      10,
        "has_sample_id":     True,
        "category_columns":  ["origin"],
        "measurement_type":  "electronic_nose",
        "has_attribution":   True,
        "has_units":         True,
    },
    "chem": {
        "filename":          "magnolia_chemical_analysis.csv",
        "sensor_count":      12,
        "has_sample_id":     True,
        "category_columns":  ["origin"],
        "measurement_type":  "chemical_analysis",
        "has_attribution":   True,
        "has_units":         True,
    },
    "bench": {
        "filename":          "electronic_tongue.csv",
        "sensor_count":      7,
        "has_sample_id":     True,
        "category_columns":  [],           # Pork benchmark has no category column
        "measurement_type":  None,
        "has_attribution":   False,
        "has_units":         False,
    },
}

PREPROCESSING_CONFIGS: dict[str, dict] = {
    "etongue": {
        "selected_features": [
            "sourness_mV", "bitterness_mV", "astringency_mV",
            "aftertaste_bitterness_mV", "aftertaste_astringency_mV",
            "umami_mV", "richness_mV", "saltiness_mV",
        ],
        "imputation_strategy": "none",
        "scaling_method":      "standard",
        "outlier_action":      "keep",
        "iqr_multiplier":      1.5,
    },
    "enose": {
        "selected_features": [
            "W1C", "W5S", "W3C", "W6S", "W5C",
            "W1S", "W1W", "W2S", "W2W", "W3S",
        ],
        "imputation_strategy": "none",
        "scaling_method":      "minmax",
        "outlier_action":      "clip",
        "iqr_multiplier":      1.5,
    },
    "chem": {
        "selected_features": [
            "syringin_mg_g", "magnoflorine_mg_g", "magnoloside_B_mg_g",
            "magnoloside_A_mg_g", "honokiol_mg_g", "magnolol_mg_g",
            "piperitylmagnolol_mg_g", "magnocurarine_mg_g",
            "beta_eudesmol_mg_g", "THM_mg_g", "PBA_ratio", "PHM_ratio",
        ],
        "imputation_strategy": "none",
        "scaling_method":      "robust",
        "outlier_action":      "remove",
        "iqr_multiplier":      1.5,
    },
    "bench": {
        "selected_features": ["AHS", "PKS", "CTS", "NMS", "CPS", "ANS", "SCS"],
        "imputation_strategy": "mean",
        "scaling_method":      "standard",
        "outlier_action":      "keep",
        "iqr_multiplier":      1.5,
    },
}

# Processed-dataset IDs saved during TEST 4, reused in tests 5–10.
# Named `saved` (not `pid`) to avoid any shell-level naming conflict.
saved: dict[str, str] = {}


# ── Locate production datasets ────────────────────────────────────

def locate_datasets() -> dict[str, dict]:
    """Return a {key: dataset_summary} mapping for all four datasets."""
    all_ds = http_get("/api/datasets")
    prod: dict[str, dict] = {}
    for ds in all_ds:
        fn = ds["original_filename"]
        for key, schema in DATASET_SCHEMAS.items():
            if fn == schema["filename"]:
                prod[key] = ds
    return prod


# ─────────────────────────────────────────────────────────────────
# TEST 1 — Dataset listing
# ─────────────────────────────────────────────────────────────────

def test_1_dataset_listing(prod: dict[str, dict]) -> None:
    section("1. Dataset listing")
    all_ds = http_get("/api/datasets")

    if len(all_ds) >= 4:
        ok(f"GET /api/datasets returns {len(all_ds)} datasets")
    else:
        fail(f"Expected ≥4 datasets, got {len(all_ds)}")

    for key, label in [
        ("etongue", "E-Tongue"), ("enose", "E-Nose"),
        ("chem", "Chemical"),    ("bench", "Benchmark"),
    ]:
        ds = prod.get(key)
        schema = DATASET_SCHEMAS[key]
        if not ds:
            fail(f"{label}: not found in list")
            continue
        ok(
            f"{label}: rows={ds['row_count']} sensors={ds['sensor_column_count']} "
            f"type={ds['measurement_type']}"
        )
        # measurement_type must match schema definition
        if ds["measurement_type"] == schema["measurement_type"]:
            ok(f"{label}: measurement_type = {ds['measurement_type']!r}")
        else:
            fail(
                f"{label}: measurement_type expected {schema['measurement_type']!r}, "
                f"got {ds['measurement_type']!r}"
            )
        # source_attribution present iff schema says so
        has_attr = bool(ds.get("source_attribution"))
        if has_attr == schema["has_attribution"]:
            ok(f"{label}: source_attribution present={has_attr} (expected)")
        else:
            fail(f"{label}: source_attribution present={has_attr}, expected={schema['has_attribution']}")


# ─────────────────────────────────────────────────────────────────
# TEST 2 — Dataset detail and statistics
# ─────────────────────────────────────────────────────────────────

def test_2_detail_and_statistics(prod: dict[str, dict]) -> None:
    section("2. Dataset detail and statistics")

    for key, label in [
        ("etongue", "E-Tongue"), ("enose", "E-Nose"),
        ("chem", "Chemical"),    ("bench", "Benchmark"),
    ]:
        ds = prod.get(key)
        schema = DATASET_SCHEMAS[key]
        if not ds:
            fail(f"{label}: dataset missing"); continue

        detail = http_get(f"/api/datasets/{ds['id']}")
        roles  = json.loads(detail["column_roles"] or "{}")
        sensors = [c for c, r in roles.items() if r == "sensor"]
        categories = [c for c, r in roles.items() if r == "category"]
        units   = json.loads(detail.get("column_units") or "{}")

        # Sensor count
        if len(sensors) == schema["sensor_count"]:
            ok(f"{label} detail: {len(sensors)} sensor columns")
        else:
            fail(f"{label} detail: expected {schema['sensor_count']} sensors, got {len(sensors)}")

        # Category columns match schema
        expected_cats = schema["category_columns"]
        if sorted(categories) == sorted(expected_cats):
            ok(f"{label} detail: category columns = {categories} (as expected)")
        else:
            fail(
                f"{label} detail: category columns expected {expected_cats}, "
                f"got {categories}"
            )

        # Units presence
        has_units = len(units) > 0
        if has_units == schema["has_units"]:
            ok(f"{label} detail: column_units present={has_units} ({len(units)} entries)")
        else:
            fail(f"{label} detail: column_units present={has_units}, expected={schema['has_units']}")

        # Statistics endpoint
        stats = http_get(f"/api/datasets/{ds['id']}/statistics")
        if len(stats["statistics"]) == schema["sensor_count"]:
            ok(f"{label} statistics: {len(stats['statistics'])} sensor stat entries returned")
        else:
            fail(
                f"{label} statistics: expected {schema['sensor_count']} entries, "
                f"got {len(stats['statistics'])}"
            )


# ─────────────────────────────────────────────────────────────────
# TEST 3 — Preview preprocessing (no save)
# ─────────────────────────────────────────────────────────────────

def test_3_preview(prod: dict[str, dict]) -> None:
    section("3. Preview preprocessing — all four datasets")

    for key, label in [
        ("etongue", "E-Tongue"), ("enose", "E-Nose"),
        ("chem", "Chemical"),    ("bench", "Benchmark"),
    ]:
        ds = prod.get(key)
        schema = DATASET_SCHEMAS[key]
        cfg    = PREPROCESSING_CONFIGS[key]
        if not ds:
            fail(f"{label} preview: dataset missing"); continue

        prev = http_post(
            "/api/preprocessing/preview",
            {"dataset_id": ds["id"], "config": cfg},
        )

        # ── 3a. sample_id column identified ──────────────────
        if schema["has_sample_id"]:
            if prev.get("sample_id_column") == "sample_id":
                ok(f"{label} preview: sample_id_column correctly identified")
            else:
                fail(
                    f"{label} preview: sample_id_column="
                    f"{prev.get('sample_id_column')!r}, expected 'sample_id'"
                )

        # ── 3b. Category columns — schema-aware check ─────────
        expected_cats = schema["category_columns"]
        actual_cats   = prev.get("category_columns", [])
        if sorted(actual_cats) == sorted(expected_cats):
            ok(
                f"{label} preview: category_columns = {actual_cats!r} "
                f"(matches schema)"
            )
        else:
            fail(
                f"{label} preview: category_columns expected {expected_cats!r}, "
                f"got {actual_cats!r}"
            )

        # ── 3c. Row counts ────────────────────────────────────
        before = prev["row_count_before"]
        after  = prev["row_count_after"]
        if key == "chem":
            # Outlier removal configured — rows must decrease
            if after < before:
                ok(f"{label} preview: outlier removal {before} → {after} rows")
            else:
                fail(f"{label} preview: expected row decrease, got {before} → {after}")
        else:
            if after == before:
                ok(f"{label} preview: row count preserved {before} → {after}")
            else:
                fail(f"{label} preview: unexpected row change {before} → {after}")

        # ── 3d. Before/after stat entries ─────────────────────
        n_feats  = len(cfg["selected_features"])
        n_stats  = len(prev["column_stats"])
        if n_stats == n_feats:
            ok(f"{label} preview: {n_stats} before/after stat entries")
        else:
            fail(f"{label} preview: expected {n_feats} stat entries, got {n_stats}")

        # ── 3e. No NaN in transformed feature columns ─────────
        cols_list = prev["columns"]
        feat_idx  = [
            cols_list.index(f)
            for f in cfg["selected_features"]
            if f in cols_list
        ]
        null_count = sum(
            1
            for row in prev["preview_rows"]
            for idx in feat_idx
            if row[idx] is None
        )
        if null_count == 0:
            ok(f"{label} preview: 0 NaN in transformed feature columns")
        else:
            fail(f"{label} preview: {null_count} NaN in transformed feature columns")

        # ── 3f. Benchmark: imputation-skip warning ────────────
        if key == "bench":
            has_warn = any(
                "no missing" in w.lower() or "skip" in w.lower()
                for w in prev.get("warnings", [])
            )
            if has_warn:
                ok(f"{label} preview: imputation-skip warning present (no missing values)")
            else:
                fail(
                    f"{label} preview: expected imputation-skip warning, "
                    f"got {prev.get('warnings')}"
                )


# ─────────────────────────────────────────────────────────────────
# TEST 4 — Apply and save
# ─────────────────────────────────────────────────────────────────

def test_4_apply_and_save(prod: dict[str, dict]) -> None:
    section("4. Apply and save")

    for key, label in [
        ("etongue", "E-Tongue"), ("enose", "E-Nose"),
        ("chem", "Chemical"),    ("bench", "Benchmark"),
    ]:
        ds  = prod.get(key)
        cfg = PREPROCESSING_CONFIGS[key]
        if not ds:
            fail(f"{label} apply: dataset missing"); continue

        result = http_post(
            "/api/preprocessing/apply",
            {"dataset_id": ds["id"], "config": cfg},
        )
        saved[key] = result["id"]   # stored in module-level dict

        # Source linkage
        if result["source_dataset_id"] == ds["id"]:
            ok(f"{label} apply: source_dataset_id correctly set")
        else:
            fail(f"{label} apply: source_dataset_id mismatch")

        # Column units round-trip
        units_saved  = json.loads(result.get("column_units") or "{}")
        src_detail   = http_get(f"/api/datasets/{ds['id']}")
        units_source = json.loads(src_detail.get("column_units") or "{}")
        if units_saved == units_source:
            ok(f"{label} apply: column units preserved ({len(units_saved)} entries)")
        else:
            fail(
                f"{label} apply: column units lost. "
                f"source={list(units_source.items())[:2]}… "
                f"saved={list(units_saved.items())[:2]}…"
            )

        # sklearn version recorded
        if result.get("sklearn_version"):
            ok(f"{label} apply: sklearn_version = {result['sklearn_version']}")
        else:
            fail(f"{label} apply: sklearn_version missing")

        # Pipeline config is valid, readable JSON with correct values
        try:
            cfg_parsed = json.loads(result["pipeline_config"])
            if cfg_parsed.get("scaling_method") == cfg["scaling_method"]:
                ok(f"{label} apply: pipeline_config JSON — scaling_method correct")
            else:
                fail(
                    f"{label} apply: scaling_method in config "
                    f"expected {cfg['scaling_method']!r}, "
                    f"got {cfg_parsed.get('scaling_method')!r}"
                )
        except Exception as exc:
            fail(f"{label} apply: pipeline_config not valid JSON: {exc}")

        # Transformations applied is a valid JSON list
        try:
            trans = json.loads(result["transformations_applied"])
            ok(f"{label} apply: transformations_applied = {len(trans)} step(s): {trans}")
        except Exception as exc:
            fail(f"{label} apply: transformations_applied not valid JSON: {exc}")


# ─────────────────────────────────────────────────────────────────
# TEST 5 — Processing history
# ─────────────────────────────────────────────────────────────────

def test_5_history(prod: dict[str, dict]) -> None:
    section("5. Processing history")

    for key, label in [
        ("etongue", "E-Tongue"), ("enose", "E-Nose"),
        ("chem", "Chemical"),    ("bench", "Benchmark"),
    ]:
        ds = prod.get(key)
        if not ds:
            fail(f"{label} history: dataset missing"); continue

        history = http_get(f"/api/preprocessing/dataset/{ds['id']}")

        if len(history) >= 1:
            ok(f"{label} history: {len(history)} processed dataset(s) in list")
        else:
            fail(f"{label} history: expected ≥1 entry, got 0")
            continue

        # Most-recent entry should be the one we just saved in TEST 4
        our_id = saved.get(key)
        if our_id and history[0]["id"] == our_id:
            ok(f"{label} history: newest entry id matches TEST 4 save")
        elif our_id:
            fail(
                f"{label} history: newest id={history[0]['id'][:8]}…, "
                f"expected={our_id[:8]}…"
            )


# ─────────────────────────────────────────────────────────────────
# TEST 6 — Get processed detail
# ─────────────────────────────────────────────────────────────────

def test_6_processed_detail() -> None:
    section("6. Get processed detail")

    for key, label in [
        ("etongue", "E-Tongue"), ("enose", "E-Nose"),
        ("chem", "Chemical"),    ("bench", "Benchmark"),
    ]:
        proc_id = saved.get(key)
        if not proc_id:
            fail(f"{label} detail: no saved id"); continue

        detail = http_get(f"/api/preprocessing/{proc_id}")
        cfg_in = PREPROCESSING_CONFIGS[key]

        # selected_features round-trip
        feats = json.loads(detail["selected_features"])
        if feats == cfg_in["selected_features"]:
            ok(f"{label} detail: selected_features round-trip ({len(feats)} columns)")
        else:
            fail(
                f"{label} detail: features mismatch "
                f"exp={cfg_in['selected_features'][:2]}… "
                f"got={feats[:2]}…"
            )

        # sklearn version readable
        if detail.get("sklearn_version"):
            ok(f"{label} detail: sklearn_version = {detail['sklearn_version']}")
        else:
            fail(f"{label} detail: sklearn_version missing")


# ─────────────────────────────────────────────────────────────────
# TEST 7 — Processed preview (paginated)
# ─────────────────────────────────────────────────────────────────

def test_7_processed_preview() -> None:
    section("7. Processed data preview (paginated)")

    # Expected total rows after processing.
    # Chemical has outlier removal so row count is variable; we just
    # check it is less than 60.  All others are deterministic.
    expected_rows: dict[str, int | None] = {
        "etongue": 60,
        "enose":   60,
        "chem":    None,   # variable — outlier removal
        "bench":   198,
    }

    for key, label in [
        ("etongue", "E-Tongue"), ("enose", "E-Nose"),
        ("chem", "Chemical"),    ("bench", "Benchmark"),
    ]:
        proc_id  = saved.get(key)
        schema   = DATASET_SCHEMAS[key]
        cfg      = PREPROCESSING_CONFIGS[key]
        exp_rows = expected_rows[key]
        if not proc_id:
            fail(f"{label} processed preview: no saved id"); continue

        pv = http_get(f"/api/preprocessing/{proc_id}/preview?page=1&page_size=20")

        # Row count
        if exp_rows is not None:
            if pv["total_rows"] == exp_rows:
                ok(f"{label} processed preview: total_rows = {pv['total_rows']}")
            else:
                fail(f"{label} processed preview: expected {exp_rows}, got {pv['total_rows']}")
        else:
            if pv["total_rows"] < 60:
                ok(f"{label} processed preview: total_rows = {pv['total_rows']} (< 60, outlier removal applied)")
            else:
                fail(f"{label} processed preview: expected < 60 rows after removal, got {pv['total_rows']}")

        # ── Schema-aware metadata column check ────────────────
        # sample_id must always be present (all four datasets have it)
        if "sample_id" in pv["columns"]:
            ok(f"{label} processed preview: sample_id column present")
        else:
            fail(f"{label} processed preview: sample_id column missing from {pv['columns'][:5]}")

        # category columns: present only if the schema expects them
        for cat_col in schema["category_columns"]:
            if cat_col in pv["columns"]:
                ok(f"{label} processed preview: category column '{cat_col}' preserved")
            else:
                fail(f"{label} processed preview: expected category column '{cat_col}' missing")

        # For benchmark: confirm no unexpected category columns were fabricated
        if not schema["category_columns"]:
            roles_in_output = {}   # we can't read roles from processed output, but
            # we can confirm sample_id is the only non-numeric looking column
            # by checking that no column named 'origin' was added
            if "origin" not in pv["columns"]:
                ok(f"{label} processed preview: no fabricated 'origin' column (correct)")
            else:
                fail(f"{label} processed preview: unexpected 'origin' column in benchmark output")

        # No NaN in sensor feature columns
        feat_idx = [
            pv["columns"].index(f)
            for f in cfg["selected_features"]
            if f in pv["columns"]
        ]
        nulls = sum(
            1
            for row in pv["rows"]
            for idx in feat_idx
            if row[idx] is None
        )
        if nulls == 0:
            ok(f"{label} processed preview: 0 NaN in sensor columns")
        else:
            fail(f"{label} processed preview: {nulls} NaN found in sensor columns")

        # Pagination — only for datasets with enough rows
        if (exp_rows is not None and exp_rows > 20) or (exp_rows is None and pv["total_rows"] > 20):
            pv2 = http_get(f"/api/preprocessing/{proc_id}/preview?page=2&page_size=20")
            if pv2["page"] == 2 and len(pv2["rows"]) > 0:
                ok(f"{label} processed preview: page 2 returned {len(pv2['rows'])} rows")
            else:
                fail(f"{label} processed preview: page 2 failed (page={pv2['page']} rows={len(pv2['rows'])})")


# ─────────────────────────────────────────────────────────────────
# TEST 8 — Original research files unchanged
# ─────────────────────────────────────────────────────────────────

def test_8_original_files_unchanged() -> None:
    section("8. Original research files unchanged")

    base_dir = Path(__file__).parent.parent / "data" / "research" / "magnolia" / "processed"
    expected_sizes = {
        "magnolia_electronic_tongue.csv": 3389,
        "magnolia_electronic_nose.csv":   4341,
        "magnolia_chemical_analysis.csv": 5273,
    }
    for fname, expected_bytes in expected_sizes.items():
        fpath = base_dir / fname
        if not fpath.exists():
            fail(f"{fname}: file not found")
            continue
        actual = fpath.stat().st_size
        if actual == expected_bytes:
            ok(f"{fname}: {actual} bytes (unchanged)")
        else:
            fail(f"{fname}: {actual} bytes, expected {expected_bytes} — MODIFIED!")


# ─────────────────────────────────────────────────────────────────
# TEST 9 — Modality separation
# ─────────────────────────────────────────────────────────────────

def test_9_modality_separation(prod: dict[str, dict]) -> None:
    section("9. Modality separation — processed datasets reference own sources")

    for key, label in [
        ("etongue", "E-Tongue"), ("enose", "E-Nose"),
        ("chem", "Chemical"),    ("bench", "Benchmark"),
    ]:
        proc_id    = saved.get(key)
        source_ds  = prod.get(key)
        if not proc_id or not source_ds:
            fail(f"{label} modality: missing ids"); continue

        detail = http_get(f"/api/preprocessing/{proc_id}")
        if detail["source_dataset_id"] == source_ds["id"]:
            ok(
                f"{label} modality: source_dataset_id → "
                f"{detail['source_filename']}"
            )
        else:
            fail(
                f"{label} modality: source mismatch "
                f"expected={source_ds['id'][:8]}… "
                f"got={detail['source_dataset_id'][:8]}…"
            )


# ─────────────────────────────────────────────────────────────────
# TEST 10 — Delete processed dataset (selective)
# ─────────────────────────────────────────────────────────────────

def test_10_delete(prod: dict[str, dict]) -> None:
    section("10. Delete processed dataset without affecting source")

    # Delete the E-Tongue processed record saved in TEST 4
    proc_id = saved.get("etongue")
    src_ds  = prod.get("etongue")
    if not proc_id:
        fail("Delete: no E-Tongue processed id available"); return

    http_delete(f"/api/preprocessing/{proc_id}")

    # Record must be gone (404)
    if http_status(f"/api/preprocessing/{proc_id}") == 404:
        ok("Delete: processed record removed from DB (404)")
    else:
        fail("Delete: processed record still accessible after delete")

    # Sibling processed records for the same source must be unaffected
    if src_ds:
        remaining = http_get(f"/api/preprocessing/dataset/{src_ds['id']}")
        deleted_still_present = any(r["id"] == proc_id for r in remaining)
        if not deleted_still_present:
            ok(f"Delete: deleted record not in history ({len(remaining)} remaining)")
        else:
            fail("Delete: deleted record still appears in history")

    # Source dataset must be fully intact
    if src_ds:
        src_status = http_status(f"/api/datasets/{src_ds['id']}")
        if src_status == 200:
            ok("Delete: source dataset unaffected (200)")
        else:
            fail(f"Delete: source dataset returned {src_status} after processed delete")


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  DravyaSense Phase 3 Workflow Test")
    print("=" * 60)

    # Verify backend is reachable
    try:
        health = http_get("/api/health")
        assert health.get("status") == "ok"
    except Exception as exc:
        print(f"\n  ERROR: Backend not reachable at {BASE}: {exc}")
        sys.exit(1)

    prod = locate_datasets()
    missing = [k for k in DATASET_SCHEMAS if k not in prod]
    if missing:
        print(f"\n  WARNING: datasets not found: {missing}")

    test_1_dataset_listing(prod)
    test_2_detail_and_statistics(prod)
    test_3_preview(prod)
    test_4_apply_and_save(prod)
    test_5_history(prod)
    test_6_processed_detail()
    test_7_processed_preview()
    test_8_original_files_unchanged()
    test_9_modality_separation(prod)
    test_10_delete(prod)

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed  |  {failed} failed")
    print(f"{'='*60}")

    if failures:
        print("\n  FAILURES:")
        for msg in failures:
            print(f"  ✗  {msg}")
        sys.exit(1)
    else:
        print("\n  All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
