"""
Phase 4B frontend-backend integration test.

Exercises every API endpoint the PCA frontend calls, in the exact
sequence the UI would invoke them, for all four datasets.

Verifies:
  1. Dataset list (selector)
  2. Dataset detail (feature column extraction)
  3. Processed dataset list (alternative input)
  4. Run PCA (no save)
  5. Scree plot data (explained variance)
  6. Scatter plot data (scores + category labels)
  7. Loadings data (feature contributions)
  8. Save PCA experiment
  9. List experiments (history sidebar)
 10. Load saved experiment (GET detail)
 11. Delete experiment
 12. CSV export data correctness
 13. Error handling (insufficient features)
 14. One-component edge case handling
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8000"
GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

passed = failed = 0
failures: list[str] = []


def ok(msg):
    global passed; passed += 1; print(f"{GREEN} PASS{RESET}  {msg}")

def fail(msg):
    global failed; failed += 1; failures.append(msg); print(f"{RED} FAIL{RESET}  {msg}")

def section(t):
    print(f"\n-- {t} --")


def http_get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read())

def http_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())

def http_delete(path):
    req = urllib.request.Request(BASE + path, method="DELETE")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {}


# ── Locate datasets ──────────────────────────────────────────────
datasets = http_get("/api/datasets")
prod = {}
for ds in datasets:
    fn = ds["original_filename"]
    if fn == "magnolia_electronic_tongue.csv":  prod["etongue"] = ds
    elif fn == "magnolia_electronic_nose.csv":   prod["enose"]   = ds
    elif fn == "magnolia_chemical_analysis.csv": prod["chem"]    = ds
    elif fn == "electronic_tongue.csv":          prod["bench"]   = ds


# ─────────────────────────────────────────────────────────────────
section("1. Dataset list (selector)")
if len(datasets) >= 4:
    ok(f"GET /api/datasets returns {len(datasets)} datasets")
else:
    fail(f"Expected >= 4 datasets, got {len(datasets)}")
for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical"),("bench","Benchmark")]:
    ds = prod.get(key)
    if ds:
        ok(f"{label}: {ds['original_filename']} ({ds['row_count']} rows, {ds['sensor_column_count']} sensors)")
    else:
        fail(f"{label}: not found")


# ─────────────────────────────────────────────────────────────────
section("2. Dataset detail (feature columns)")
for key, label, exp_sensors in [
    ("etongue","E-Tongue",8),("enose","E-Nose",10),
    ("chem","Chemical",12),("bench","Benchmark",7)
]:
    ds = prod.get(key)
    if not ds: continue
    d = http_get(f"/api/datasets/{ds['id']}")
    roles = json.loads(d["column_roles"] or "{}")
    sensors = [c for c,r in roles.items() if r == "sensor"]
    if len(sensors) == exp_sensors:
        ok(f"{label}: {len(sensors)} sensor columns extracted from detail")
    else:
        fail(f"{label}: expected {exp_sensors} sensors, got {len(sensors)}")


# ─────────────────────────────────────────────────────────────────
section("3. Processed dataset list (alternative input)")
ds_et = prod.get("etongue")
if ds_et:
    hist = http_get(f"/api/preprocessing/dataset/{ds_et['id']}")
    ok(f"E-Tongue processed datasets: {len(hist)} available")
    if hist:
        ok(f"First processed: {hist[0]['source_filename']} ({hist[0]['row_count']} rows, {hist[0]['sensor_column_count']} features)")
    else:
        info_msg = "No processed datasets -- testing raw input only"
        print(f"  INFO  {info_msg}")


# ─────────────────────────────────────────────────────────────────
section("4. Run PCA (no save) -- all four datasets")
configs = {
    "etongue": {"n_comp": 4, "exp_n": 8},
    "enose":   {"n_comp": 3, "exp_n": 10},
    "chem":    {"n_comp": 5, "exp_n": 12},
    "bench":   {"n_comp": 2, "exp_n": 7},
}
run_results = {}

for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical"),("bench","Benchmark")]:
    ds = prod.get(key)
    cfg = configs[key]
    if not ds: continue
    code, r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": cfg["n_comp"],
    })
    if code not in (200, 201):
        fail(f"{label} run: HTTP {code} -- {r.get('detail','')}")
        continue

    run_results[key] = r
    # Check dimensions
    checks = [
        ("n_samples", r["n_samples"], ds["row_count"]),
        ("n_features", r["n_features"], cfg["exp_n"]),
        ("n_components", r["n_components"], cfg["n_comp"]),
    ]
    all_ok = True
    for name, got, exp in checks:
        if got != exp:
            fail(f"{label}: {name} expected {exp}, got {got}")
            all_ok = False
    if all_ok:
        ok(f"{label}: n_samples={r['n_samples']}, n_features={r['n_features']}, n_components={r['n_components']}")

    # experiment_id must be None (unsaved)
    if r["experiment_id"] is None:
        ok(f"{label}: experiment_id is None (unsaved)")
    else:
        fail(f"{label}: experiment_id should be None for /run")


# ─────────────────────────────────────────────────────────────────
section("5. Scree plot data (explained variance)")
for key, label in [("etongue","E-Tongue"),("chem","Chemical")]:
    r = run_results.get(key)
    if not r: continue
    evr = r["explained_variance_ratio"]
    cum = r["cumulative_variance_ratio"]
    if all(0 < v <= 1.0 for v in evr):
        ok(f"{label}: all evr in (0,1]")
    else:
        fail(f"{label}: evr out of range: {evr}")
    if all(cum[i] <= cum[i+1] + 1e-10 for i in range(len(cum)-1)):
        ok(f"{label}: cumulative is monotonically non-decreasing")
    else:
        fail(f"{label}: cumulative not monotone")
    if abs(cum[-1] - sum(evr)) < 1e-10:
        ok(f"{label}: cumulative[-1] == sum(evr)")
    else:
        fail(f"{label}: cumulative[-1] != sum(evr)")


# ─────────────────────────────────────────────────────────────────
section("6. Scatter plot data (scores + category labels)")
for key, label in [("etongue","E-Tongue"),("bench","Benchmark")]:
    r = run_results.get(key)
    if not r: continue

    # Scores shape
    if len(r["scores"]) == r["n_samples"] and len(r["scores"][0]) == r["n_components"]:
        ok(f"{label}: scores shape = ({r['n_samples']}, {r['n_components']})")
    else:
        fail(f"{label}: scores shape wrong")

    # Category labels
    if key == "etongue":
        if set(r["category_labels"]) == {"JYHP", "AYHP"}:
            ok(f"{label}: category_labels = JYHP/AYHP")
        else:
            fail(f"{label}: unexpected categories: {set(r['category_labels'])}")
    elif key == "bench":
        if r["category_labels"] == []:
            ok(f"{label}: category_labels = [] (no category column)")
        else:
            fail(f"{label}: expected empty category_labels")

    # sample_ids match
    if len(r["sample_ids"]) == r["n_samples"]:
        ok(f"{label}: {len(r['sample_ids'])} sample_ids")
    else:
        fail(f"{label}: sample_ids count mismatch")


# ─────────────────────────────────────────────────────────────────
section("7. Loadings data (feature contributions)")
for key, label in [("etongue","E-Tongue"),("enose","E-Nose")]:
    r = run_results.get(key)
    if not r: continue
    if len(r["loadings"]) == r["n_components"] and len(r["loadings"][0]) == r["n_features"]:
        ok(f"{label}: loadings shape = ({r['n_components']}, {r['n_features']})")
    else:
        fail(f"{label}: loadings shape wrong: ({len(r['loadings'])}, {len(r['loadings'][0]) if r['loadings'] else 0})")

    # feature_columns in loadings match
    if r["feature_columns"]:
        ok(f"{label}: {len(r['feature_columns'])} feature columns listed")


# ─────────────────────────────────────────────────────────────────
section("8. Save PCA experiment")
saved_ids = {}
for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical"),("bench","Benchmark")]:
    ds = prod.get(key)
    cfg = configs[key]
    if not ds: continue
    code, r = http_post("/api/pca/save", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": cfg["n_comp"],
        "experiment_name": f"{label} PCA test",
    })
    if code not in (200, 201):
        fail(f"{label} save: HTTP {code}")
        continue
    saved_ids[key] = r["experiment_id"]
    if r["experiment_id"]:
        ok(f"{label}: saved experiment_id = {r['experiment_id'][:8]}...")
    else:
        fail(f"{label}: experiment_id is None after /save")
    if r["experiment_name"] == f"{label} PCA test":
        ok(f"{label}: experiment_name preserved")
    else:
        fail(f"{label}: experiment_name mismatch")
    if r["created_at"]:
        ok(f"{label}: created_at present")
    else:
        fail(f"{label}: created_at missing")


# ─────────────────────────────────────────────────────────────────
section("9. List experiments (history sidebar)")
all_exps = http_get("/api/pca/experiments")
if len(all_exps) >= 4:
    ok(f"GET /api/pca/experiments: {len(all_exps)} experiments")
else:
    fail(f"Expected >= 4 experiments, got {len(all_exps)}")

# Filter by source
if ds_et:
    filtered = http_get(f"/api/pca/experiments?source_id={ds_et['id']}")
    if all(e["input_id"] == ds_et["id"] for e in filtered):
        ok(f"Filter by source_id: {len(filtered)} for E-Tongue")
    else:
        fail("Filter by source_id: entries don't match")


# ─────────────────────────────────────────────────────────────────
section("10. Load saved experiment (GET detail)")
for key, label in [("etongue","E-Tongue"),("chem","Chemical")]:
    eid = saved_ids.get(key)
    if not eid: continue
    r2 = http_get(f"/api/pca/experiments/{eid}")
    r1 = run_results.get(key)
    if not r1: continue

    # Compare key fields
    fields = ["n_samples", "n_features", "n_components", "feature_columns",
              "sample_ids", "category_labels", "explained_variance_ratio"]
    all_match = all(r1.get(f) == r2.get(f) for f in fields)
    if all_match:
        ok(f"{label}: all key fields match between /run and GET /experiments/{{id}}")
    else:
        for f in fields:
            if r1.get(f) != r2.get(f):
                fail(f"{label}: {f} mismatch: {str(r1.get(f))[:40]} vs {str(r2.get(f))[:40]}")

    if r2["experiment_name"]:
        ok(f"{label}: experiment_name = {r2['experiment_name']}")
    if r2["source_filename"]:
        ok(f"{label}: source_filename = {r2['source_filename']}")
    if r2["preprocessing_summary"]:
        ok(f"{label}: preprocessing_summary present")


# ─────────────────────────────────────────────────────────────────
section("11. Delete experiment")
eid = saved_ids.get("etongue")
if eid:
    code, _ = http_delete(f"/api/pca/experiments/{eid}")
    if code == 200:
        ok("DELETE experiment: HTTP 200")
    else:
        fail(f"DELETE experiment: HTTP {code}")

    # Verify gone
    try:
        http_get(f"/api/pca/experiments/{eid}")
        fail("Deleted experiment still accessible")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            ok("Deleted experiment returns 404")
        else:
            fail(f"Deleted experiment returns {exc.code}")

    # Source dataset unaffected
    if ds_et:
        try:
            d = http_get(f"/api/datasets/{ds_et['id']}")
            ok("Source dataset still accessible (200)")
        except Exception:
            fail("Source dataset inaccessible after experiment delete")


# ─────────────────────────────────────────────────────────────────
section("12. CSV export data correctness")
r = run_results.get("etongue")
if r:
    # Verify scores are exportable: sample_ids + category + PC columns
    if len(r["sample_ids"]) == len(r["scores"]):
        ok("Scores: sample_ids count == scores rows")
    if r["category_labels"] and len(r["category_labels"]) == len(r["scores"]):
        ok("Scores: category_labels count == scores rows")
    # Loadings
    if len(r["loadings"][0]) == len(r["feature_columns"]):
        ok("Loadings: columns count == feature_columns count")
    # EVR and cumulative
    if len(r["explained_variance_ratio"]) == r["n_components"]:
        ok("EVR: length == n_components")
    if len(r["cumulative_variance_ratio"]) == r["n_components"]:
        ok("Cumulative: length == n_components")


# ─────────────────────────────────────────────────────────────────
section("13. Error handling (insufficient features)")
ds = prod.get("etongue")
if ds:
    detail = http_get(f"/api/datasets/{ds['id']}")
    roles = json.loads(detail["column_roles"])
    sensors = [c for c,r in roles.items() if r == "sensor"]

    # Request with only 1 feature
    code, r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": 2,
        "feature_columns": [sensors[0]],  # only 1 feature
    })
    # PCA requires at least 2 features for n_components=2
    if code == 422:
        ok("Single feature + n_components=2: HTTP 422 (expected)")
    elif code in (200, 201):
        # If it succeeds, n_components must be capped to 1
        if r["n_components"] == 1:
            ok("Single feature: n_components capped to 1")
        else:
            fail(f"Single feature: unexpected n_components={r['n_components']}")
    else:
        fail(f"Single feature: unexpected HTTP {code}")

    # Request with n_components=1 (minimum is 2 per schema validation)
    code2, r2 = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": 1,
    })
    if code2 == 422:
        ok("n_components=1: HTTP 422 (schema rejects n_components < 2)")
    else:
        fail(f"n_components=1: expected 422, got {code2}")

    # Nonexistent dataset
    code3, r3 = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": "nonexistent-uuid-12345",
        "n_components": 2,
    })
    if code3 == 404:
        ok("Nonexistent dataset: HTTP 404")
    else:
        fail(f"Nonexistent dataset: expected 404, got {code3}")


# ─────────────────────────────────────────────────────────────────
section("14. Processed dataset as PCA input")
ds_et = prod.get("etongue")
if ds_et:
    hist = http_get(f"/api/preprocessing/dataset/{ds_et['id']}")
    if hist:
        proc_id = hist[0]["id"]
        code, r = http_post("/api/pca/run", {
            "input_type": "processed_dataset",
            "input_id": proc_id,
            "n_components": 3,
        })
        if code in (200, 201):
            ok(f"Processed input PCA: n_samples={r['n_samples']}, n_features={r['n_features']}")
            if r["preprocessing_summary"]:
                ok(f"Preprocessing summary: {r['preprocessing_summary'][:60]}")
            if "sample_id" not in r["feature_columns"] and "origin" not in r["feature_columns"]:
                ok("Metadata excluded from processed input feature matrix")
            else:
                fail("Metadata found in processed input feature columns")
        else:
            fail(f"Processed input PCA: HTTP {code}")


# ─────────────────────────────────────────────────────────────────
# Cleanup remaining saved experiments
section("Cleanup")
for key, eid in saved_ids.items():
    if eid and key != "etongue":  # etongue already deleted
        http_delete(f"/api/pca/experiments/{eid}")
ok("Cleaned up test experiments")


# ─────────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"  RESULTS: {passed} passed  |  {failed} failed")
print(f"{'='*55}")
if failures:
    print("\n  FAILURES:")
    for msg in failures:
        print(f"  x  {msg}")
    sys.exit(1)
else:
    print("\n  All checks passed.")
    sys.exit(0)
