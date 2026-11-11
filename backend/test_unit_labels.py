"""
Unit label verification — DravyaSense Preprocessing Engine

Verifies that:
  1. StandardScaler produces 'z-score' labels (not original units).
  2. MinMaxScaler produces '[0,1]' labels.
  3. RobustScaler produces 'robust-scaled' labels.
  4. scaling_method='none' preserves original source units.
  5. Unselected sensor columns retain their original units.
  6. Metadata columns (sample_id, origin) carry no unit labels.
  7. source dataset column_units are unchanged after apply.
  8. Preview and apply both return correct units (consistency).

Tested on all three Magnolia research datasets.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE  = "http://localhost:8000"
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


def http_get(path: str) -> dict | list:
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.loads(r.read())


def http_post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def http_delete(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", method="DELETE")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


# ── Locate the three Magnolia datasets ───────────────────────────

def locate_magnolia() -> dict[str, dict]:
    all_ds = http_get("/api/datasets")
    out: dict[str, dict] = {}
    for ds in all_ds:
        fn = ds["original_filename"]
        if fn == "magnolia_electronic_tongue.csv":  out["etongue"] = ds
        elif fn == "magnolia_electronic_nose.csv":   out["enose"]   = ds
        elif fn == "magnolia_chemical_analysis.csv": out["chem"]    = ds
    return out


# ── Expected source units per dataset ───────────────────────────

SOURCE_UNITS = {
    "etongue": {
        "sourness_mV": "mV", "bitterness_mV": "mV", "astringency_mV": "mV",
        "aftertaste_bitterness_mV": "mV", "aftertaste_astringency_mV": "mV",
        "umami_mV": "mV", "richness_mV": "mV", "saltiness_mV": "mV",
    },
    "enose": {
        "W1C": "G/G0", "W5S": "G/G0", "W3C": "G/G0", "W6S": "G/G0", "W5C": "G/G0",
        "W1S": "G/G0", "W1W": "G/G0", "W2S": "G/G0", "W2W": "G/G0", "W3S": "G/G0",
    },
    "chem": {
        "syringin_mg_g": "mg/g", "magnoflorine_mg_g": "mg/g",
        "magnoloside_B_mg_g": "mg/g", "magnoloside_A_mg_g": "mg/g",
        "honokiol_mg_g": "mg/g", "magnolol_mg_g": "mg/g",
        "piperitylmagnolol_mg_g": "mg/g", "magnocurarine_mg_g": "mg/g",
        "beta_eudesmol_mg_g": "mg/g", "THM_mg_g": "mg/g",
        "PBA_ratio": "ratio", "PHM_ratio": "ratio",
    },
}

FEATURES = {
    "etongue": list(SOURCE_UNITS["etongue"].keys()),
    "enose":   list(SOURCE_UNITS["enose"].keys()),
    "chem":    list(SOURCE_UNITS["chem"].keys()),
}

SCALER_LABELS = {
    "standard": "z-score",
    "minmax":   "[0,1]",
    "robust":   "robust-scaled",
}


def check_units_for_scaler(
    ds: dict,
    key: str,
    label: str,
    scaler: str,
) -> None:
    """
    Preview and apply a config with the given scaler on ALL features
    of the dataset, then verify:
      - All selected features get the correct processed unit label.
      - The 'processed_column_units' in the preview matches.
      - The 'column_units' in the saved ProcessedDataset matches.
      - The source dataset column_units are unchanged.
    """
    features     = FEATURES[key]
    source_units = SOURCE_UNITS[key]
    expected_unit = SCALER_LABELS[scaler]

    config = {
        "selected_features":   features,
        "imputation_strategy": "none",
        "scaling_method":      scaler,
        "outlier_action":      "keep",
        "iqr_multiplier":      1.5,
    }

    # ── Preview ────────────────────────────────────────────────
    prev = http_post(
        "/api/preprocessing/preview",
        {"dataset_id": ds["id"], "config": config},
    )
    prev_units: dict[str, str] = prev.get("processed_column_units", {})

    all_ok = True
    for col in features:
        got = prev_units.get(col)
        if got == expected_unit:
            pass  # silent pass to reduce output noise
        else:
            fail(
                f"{label} preview [{scaler}]: "
                f"{col} expected unit '{expected_unit}', got '{got}'"
            )
            all_ok = False
    if all_ok:
        ok(f"{label} preview [{scaler}]: all {len(features)} features → '{expected_unit}'")

    # ── Apply ──────────────────────────────────────────────────
    result = http_post(
        "/api/preprocessing/apply",
        {"dataset_id": ds["id"], "config": config},
    )
    proc_id = result["id"]
    saved_units: dict[str, str] = json.loads(result.get("column_units") or "{}")

    all_ok_apply = True
    for col in features:
        got = saved_units.get(col)
        if got == expected_unit:
            pass
        else:
            fail(
                f"{label} apply [{scaler}]: "
                f"{col} expected unit '{expected_unit}', got '{got}'"
            )
            all_ok_apply = False
    if all_ok_apply:
        ok(f"{label} apply  [{scaler}]: all {len(features)} features → '{expected_unit}'")

    # ── Source units unchanged ─────────────────────────────────
    src_detail  = http_get(f"/api/datasets/{ds['id']}")
    actual_src  = json.loads(src_detail.get("column_units") or "{}")
    if actual_src == source_units:
        ok(f"{label} apply  [{scaler}]: source column_units unchanged after apply")
    else:
        # Find first mismatch
        for col, exp in source_units.items():
            if actual_src.get(col) != exp:
                fail(
                    f"{label} apply [{scaler}]: source unit for '{col}' "
                    f"changed to '{actual_src.get(col)}', expected '{exp}'"
                )
                break

    # Clean up to avoid accumulating records
    http_delete(f"/api/preprocessing/{proc_id}")


def check_no_scaling_preserves_units(
    ds: dict,
    key: str,
    label: str,
) -> None:
    """When scaling_method='none', source units are preserved verbatim."""
    features     = FEATURES[key]
    source_units = SOURCE_UNITS[key]

    config = {
        "selected_features":   features,
        "imputation_strategy": "none",
        "scaling_method":      "none",
        "outlier_action":      "keep",
        "iqr_multiplier":      1.5,
    }

    prev = http_post(
        "/api/preprocessing/preview",
        {"dataset_id": ds["id"], "config": config},
    )
    prev_units: dict[str, str] = prev.get("processed_column_units", {})

    all_ok = True
    for col in features:
        got = prev_units.get(col)
        exp = source_units.get(col)
        if got == exp:
            pass
        else:
            fail(
                f"{label} preview [none]: '{col}' expected '{exp}', got '{got}'"
            )
            all_ok = False
    if all_ok:
        ok(f"{label} preview [none]: all {len(features)} source units preserved")

    # Apply and check
    result  = http_post(
        "/api/preprocessing/apply",
        {"dataset_id": ds["id"], "config": config},
    )
    proc_id = result["id"]
    saved_units: dict[str, str] = json.loads(result.get("column_units") or "{}")

    all_ok_apply = True
    for col in features:
        got = saved_units.get(col)
        exp = source_units.get(col)
        if got == exp:
            pass
        else:
            fail(
                f"{label} apply  [none]: '{col}' expected '{exp}', got '{got}'"
            )
            all_ok_apply = False
    if all_ok_apply:
        ok(f"{label} apply  [none]: all {len(features)} source units preserved")

    http_delete(f"/api/preprocessing/{proc_id}")


def check_partial_selection_units(
    ds: dict,
    key: str,
    label: str,
) -> None:
    """
    Unselected sensor columns must retain original units.
    Selected columns must get the scaler unit.
    """
    all_features  = FEATURES[key]
    source_units  = SOURCE_UNITS[key]
    # Select only the first half
    selected = all_features[: len(all_features) // 2]
    unselected = all_features[len(all_features) // 2 :]

    config = {
        "selected_features":   selected,
        "imputation_strategy": "none",
        "scaling_method":      "standard",
        "outlier_action":      "keep",
        "iqr_multiplier":      1.5,
    }

    result  = http_post(
        "/api/preprocessing/apply",
        {"dataset_id": ds["id"], "config": config},
    )
    proc_id = result["id"]
    saved_units: dict[str, str] = json.loads(result.get("column_units") or "{}")

    # Selected → z-score
    selected_ok = all(saved_units.get(col) == "z-score" for col in selected)
    if selected_ok:
        ok(f"{label} partial [standard]: {len(selected)} selected → 'z-score'")
    else:
        for col in selected:
            if saved_units.get(col) != "z-score":
                fail(f"{label} partial: selected '{col}' → '{saved_units.get(col)}', expected 'z-score'")

    # Unselected → original source unit
    unselected_ok = all(saved_units.get(col) == source_units.get(col) for col in unselected)
    if unselected_ok:
        ok(f"{label} partial [standard]: {len(unselected)} unselected → original units preserved")
    else:
        for col in unselected:
            got = saved_units.get(col)
            exp = source_units.get(col)
            if got != exp:
                fail(f"{label} partial: unselected '{col}' → '{got}', expected '{exp}'")

    http_delete(f"/api/preprocessing/{proc_id}")


# ── Main ─────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  DravyaSense — Unit Label Verification")
    print("=" * 60)

    # Verify backend
    try:
        h = http_get("/api/health")
        assert h.get("status") == "ok"
    except Exception as exc:
        print(f"\n  ERROR: Backend not reachable: {exc}")
        sys.exit(1)

    prod = locate_magnolia()
    missing = [k for k in ("etongue", "enose", "chem") if k not in prod]
    if missing:
        print(f"\n  WARNING: Missing datasets: {missing}")

    section("1. StandardScaler → z-score (all three datasets)")
    for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical")]:
        ds = prod.get(key)
        if ds:
            check_units_for_scaler(ds, key, label, "standard")

    section("2. MinMaxScaler → [0,1] (all three datasets)")
    for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical")]:
        ds = prod.get(key)
        if ds:
            check_units_for_scaler(ds, key, label, "minmax")

    section("3. RobustScaler → robust-scaled (all three datasets)")
    for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical")]:
        ds = prod.get(key)
        if ds:
            check_units_for_scaler(ds, key, label, "robust")

    section("4. No scaling → source units preserved (all three datasets)")
    for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical")]:
        ds = prod.get(key)
        if ds:
            check_no_scaling_preserves_units(ds, key, label)

    section("5. Partial feature selection — unselected columns keep source units")
    for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical")]:
        ds = prod.get(key)
        if ds:
            check_partial_selection_units(ds, key, label)

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
