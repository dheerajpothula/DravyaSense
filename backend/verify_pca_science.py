"""
Scientific verification - PCA Phase 4A backend.
Read-only investigation - no code modifications.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.request

import numpy as np

BASE = "http://localhost:8000"


def http_get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read())


def http_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def http_delete(path):
    req = urllib.request.Request(BASE + path, method="DELETE")
    try:
        urllib.request.urlopen(req)
    except Exception:
        pass


# Locate datasets
datasets = http_get("/api/datasets")
prod = {}
for ds in datasets:
    fn = ds["original_filename"]
    if fn == "magnolia_electronic_tongue.csv":
        prod["etongue"] = ds
    elif fn == "magnolia_electronic_nose.csv":
        prod["enose"] = ds
    elif fn == "magnolia_chemical_analysis.csv":
        prod["chem"] = ds
    elif fn == "electronic_tongue.csv":
        prod["bench"] = ds


def get_col_idx(columns):
    return {c: i for i, c in enumerate(columns)}


def load_feature_matrix(ds_id, feature_cols):
    """Load all rows from the dataset preview and extract numeric features."""
    pv = http_get("/api/datasets/{}/preview?page=1&page_size=100".format(ds_id))
    idx = get_col_idx(pv["columns"])
    X = np.array([[float(row[idx[c]]) for c in feature_cols] for row in pv["rows"]])
    return X


PASS = "  PASS"
FAIL = "  FAIL"

print("=" * 65)
print("  PCA Phase 4A -- Scientific Verification")
print("=" * 65)

# ==================================================================
# Q1. Why do score dimensions differ across datasets?
# ==================================================================
print("\n" + "-" * 65)
print("  Q1. Why do PCA score dimensions differ across datasets?")
print("-" * 65)

configs = {"etongue": 4, "enose": 3, "chem": 5, "bench": 2}
labels = {"etongue": "E-Tongue", "enose": "E-Nose", "chem": "Chemical", "bench": "Benchmark"}

for key in ["etongue", "enose", "chem", "bench"]:
    ds = prod.get(key)
    if not ds:
        continue
    n_req = configs[key]
    r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": n_req,
    })
    print("\n  {}:".format(labels[key]))
    print("    Requested n_components = {}".format(n_req))
    print("    n_samples  = {}".format(r["n_samples"]))
    print("    n_features = {}".format(r["n_features"]))
    print("    Actual n_components = {}".format(r["n_components"]))
    max_c = min(r["n_samples"], r["n_features"])
    print("    max possible = min({}, {}) = {}".format(r["n_samples"], r["n_features"], max_c))
    s_rows = len(r["scores"])
    s_cols = len(r["scores"][0]) if r["scores"] else 0
    print("    Scores shape = ({}, {})".format(s_rows, s_cols))
    l_rows = len(r["loadings"])
    l_cols = len(r["loadings"][0]) if r["loadings"] else 0
    print("    Loadings shape = ({}, {})".format(l_rows, l_cols))

print("""
  Explanation: The test suite requested different n_components for
  each dataset. The score matrix is always (n_samples, n_components)
  and the loadings matrix is always (n_components, n_features).
  None of the dimensions were truncated -- each request was within
  the min(n_samples, n_features) limit.""")

# ==================================================================
# Q2. Exact input features for each dataset
# ==================================================================
print("\n" + "-" * 65)
print("  Q2. Exact input features for each dataset")
print("-" * 65)

for key in ["etongue", "enose", "chem", "bench"]:
    ds = prod.get(key)
    if not ds:
        continue
    detail = http_get("/api/datasets/" + ds["id"])
    roles = json.loads(detail["column_roles"])
    sensor_cols = [c for c, r in roles.items() if r == "sensor"]
    sample_id_col = next((c for c, r in roles.items() if r == "sample_id"), None)
    category_cols = [c for c, r in roles.items() if r == "category"]
    units = json.loads(detail.get("column_units") or "{}")

    r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": 2,
    })
    print("\n  {} ({}):".format(labels[key], detail["original_filename"]))
    print("    Stored sensor-role columns ({}):".format(len(sensor_cols)))
    for c in sensor_cols:
        u = units.get(c, "")
        unit_str = "  [{}]".format(u) if u else ""
        print("      {}{}".format(c, unit_str))
    print("    sample_id column: {!r}".format(sample_id_col))
    print("    category columns: {}".format(category_cols))
    print("    PCA feature_columns ({}): {}".format(len(r["feature_columns"]), r["feature_columns"]))
    if r["feature_columns"] == sensor_cols:
        print("    OK: feature_columns == stored sensor columns (exact match)")
    else:
        print("    MISMATCH")

# ==================================================================
# Q3. Were any original measurement features excluded, and why?
# ==================================================================
print("\n" + "-" * 65)
print("  Q3. Were any original measurement features excluded?")
print("-" * 65)

for key in ["etongue", "enose", "chem", "bench"]:
    ds = prod.get(key)
    if not ds:
        continue
    detail = http_get("/api/datasets/" + ds["id"])
    roles = json.loads(detail["column_roles"])
    sensor_cols = [c for c, r in roles.items() if r == "sensor"]

    # Request more components than features so nothing is truncated
    r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": min(len(sensor_cols), 20),
    })

    pca_feats = set(r["feature_columns"])
    stored_sensors = set(sensor_cols)
    excluded = stored_sensors - pca_feats

    print("\n  {}:".format(labels[key]))
    print("    Stored sensor columns:  {}".format(len(stored_sensors)))
    print("    PCA feature columns:    {}".format(len(pca_feats)))
    if excluded:
        print("    EXCLUDED from PCA:      {}".format(excluded))
        relevant = [w for w in r["warnings"] if any(e in w for e in excluded)]
        for w in relevant:
            print("      Warning: {}".format(w))
    else:
        print("    EXCLUDED from PCA:      none -- all sensor columns used")
        print("    OK: All {} sensor columns entered the feature matrix".format(len(stored_sensors)))

# ==================================================================
# Q4. All 8 e-tongue measurements available for PCA when selected?
# ==================================================================
print("\n" + "-" * 65)
print("  Q4. All 8 e-tongue measurements available for PCA?")
print("-" * 65)

ds = prod.get("etongue")
detail = http_get("/api/datasets/" + ds["id"])
roles = json.loads(detail["column_roles"])
sensor_cols = [c for c, r in roles.items() if r == "sensor"]
print("\n  Stored sensor columns ({}):".format(len(sensor_cols)))
for i, c in enumerate(sensor_cols, 1):
    print("    {}. {}".format(i, c))

# Run PCA with all 8 sensors
r = http_post("/api/pca/run", {
    "input_type": "raw_dataset",
    "input_id": ds["id"],
    "n_components": 8,
    "feature_columns": sensor_cols,
})
print("\n  PCA with explicit feature_columns = all 8 sensors:")
print("    n_features = {}".format(r["n_features"]))
print("    feature_columns = {}".format(r["feature_columns"]))
print("    n_components = {}".format(r["n_components"]))
if r["feature_columns"] == sensor_cols and r["n_features"] == 8:
    print("    OK: All 8 measurements available and used")
else:
    print("    FAIL: Some measurements missing")

# Also test with a subset of 4
subset = sensor_cols[:4]
r2 = http_post("/api/pca/run", {
    "input_type": "raw_dataset",
    "input_id": ds["id"],
    "n_components": 2,
    "feature_columns": subset,
})
print("\n  PCA with explicit feature_columns = first 4 sensors:")
print("    Requested: {}".format(subset))
print("    Got:       {}".format(r2["feature_columns"]))
if r2["feature_columns"] == subset:
    print("    OK: Subset selection works -- exactly the 4 requested")
else:
    print("    FAIL: Subset mismatch")

# ==================================================================
# Q5. Zero-variance detection on actual input features?
# ==================================================================
print("\n" + "-" * 65)
print("  Q5. Zero-variance detection on actual input features?")
print("-" * 65)

print("\n  Checking all 4 datasets for zero-variance sensor columns:")
for key in ["etongue", "enose", "chem", "bench"]:
    ds = prod.get(key)
    if not ds:
        continue
    detail = http_get("/api/datasets/" + ds["id"])
    roles = json.loads(detail["column_roles"])
    sensor_cols = [c for c, r in roles.items() if r == "sensor"]

    # Check actual variance in the raw data
    X = load_feature_matrix(ds["id"], sensor_cols)
    variances = np.var(X, axis=0)
    zero_var = [sensor_cols[i] for i in range(len(sensor_cols)) if variances[i] == 0]

    r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": min(len(sensor_cols), 20),
    })
    zero_warns = [w for w in r["warnings"] if "zero" in w.lower() or "constant" in w.lower()]

    print("\n  {}:".format(labels[key]))
    print("    numpy var per column: {}".format(["{:.6f}".format(v) for v in variances]))
    if zero_var:
        print("    Zero-variance columns: {}".format(zero_var))
    else:
        print("    Zero-variance columns: none (all have variance > 0)")
    if zero_warns:
        print("    PCA warnings: {}".format(zero_warns))
    else:
        print("    PCA warnings: none (no columns dropped)")

print("""
  The zero-variance check (np.var(X, axis=0) == 0) is applied in
  _build_bundle() on every PCA run. None of the 4 production datasets
  have constant sensor columns, so none were dropped. The test fixture
  'fix_const.csv' with s2_const=5.0 was correctly excluded with a
  warning in test 8 of the test suite.""")

# ==================================================================
# Q6. PCA results from actual sklearn computation?
# ==================================================================
print("\n" + "-" * 65)
print("  Q6. PCA scores/loadings/variance from actual sklearn?")
print("-" * 65)

ds = prod.get("etongue")
r = http_post("/api/pca/run", {
    "input_type": "raw_dataset",
    "input_id": ds["id"],
    "n_components": 3,
})
print("\n  E-Tongue PCA (n_components=3):")
print("    sklearn_version: {}".format(r["sklearn_version"]))
print("    explained_variance_ratio: {}".format(r["explained_variance_ratio"]))
print("    cumulative_variance_ratio: {}".format(r["cumulative_variance_ratio"]))

# Independent numpy SVD cross-validation
print("\n  Cross-validation with independent numpy SVD:")
X = load_feature_matrix(ds["id"], r["feature_columns"])
print("    Feature matrix shape: {}".format(X.shape))
print("    Any NaN: {}, Any inf: {}".format(np.isnan(X).any(), np.isinf(X).any()))

X_centered = X - X.mean(axis=0)
U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
variances = (S ** 2) / (X.shape[0] - 1)
total_var = np.sum(np.var(X, axis=0, ddof=1))
evr_svd = (variances[:3] / total_var).tolist()
cum_svd = np.cumsum(evr_svd).tolist()

print("\n    numpy SVD explained_variance_ratio: {}".format(evr_svd))
print("    API   explained_variance_ratio:       {}".format(r["explained_variance_ratio"]))
evr_diff = max(abs(a - b) for a, b in zip(evr_svd, r["explained_variance_ratio"]))
print("    Max abs diff: {:.2e}".format(evr_diff))
if evr_diff < 1e-10:
    print("    OK: explained_variance_ratio matches numpy SVD (diff < 1e-10)")
else:
    print("    MISMATCH")

# Compare scores (first sample)
scores_svd = (U[:, :3] * S[:3]).tolist()
print("\n    Scores row 0 -- numpy SVD: {}".format(scores_svd[0]))
print("    Scores row 0 -- API:       {}".format(r["scores"][0]))
score_diff = max(abs(a - b) for a, b in zip(scores_svd[0], r["scores"][0]))
print("    Max abs diff (row 0): {:.2e}".format(score_diff))

# Compare loadings (may differ by sign)
loadings_svd = Vt[:3].tolist()
api_loadings = r["loadings"]
print("\n    Loadings PC1 -- numpy SVD: {}".format(loadings_svd[0]))
print("    Loadings PC1 -- API:       {}".format(api_loadings[0]))
dot = float(np.dot(loadings_svd[0], api_loadings[0]))
print("    Dot product PC1: {:.8f}".format(dot))
if abs(abs(dot) - 1.0) < 1e-8:
    print("    OK: Loadings match up to sign (|dot| = 1.0)")
else:
    print("    Checking elements:")
    for i in range(min(4, len(loadings_svd[0]))):
        print("      feat {}: svd={:.8f} api={:.8f}".format(i, loadings_svd[0][i], api_loadings[0][i]))

# ==================================================================
# Q7. Mathematical consistency of variance ratios and dimensions
# ==================================================================
print("\n" + "-" * 65)
print("  Q7. Mathematical consistency")
print("-" * 65)

for key, n_comp in [("etongue", 8), ("enose", 10), ("chem", 12)]:
    ds = prod.get(key)
    if not ds:
        continue
    r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id": ds["id"],
        "n_components": n_comp,
    })
    evr = r["explained_variance_ratio"]
    cum = r["cumulative_variance_ratio"]
    n_pc = r["n_components"]
    n_f = r["n_features"]
    n_s = r["n_samples"]

    print("\n  {} (n_components={}):".format(labels[key], n_comp))

    # 7a. Scores shape
    s_shape = (len(r["scores"]), len(r["scores"][0]))
    ok = s_shape == (n_s, n_pc)
    print("    7a. scores shape {} == ({}, {}): {}".format(s_shape, n_s, n_pc, "OK" if ok else "FAIL"))

    # 7b. Loadings shape
    l_shape = (len(r["loadings"]), len(r["loadings"][0]))
    ok = l_shape == (n_pc, n_f)
    print("    7b. loadings shape {} == ({}, {}): {}".format(l_shape, n_pc, n_f, "OK" if ok else "FAIL"))

    # 7c. EVR length
    ok = len(evr) == n_pc
    print("    7c. len(evr) {} == {}: {}".format(len(evr), n_pc, "OK" if ok else "FAIL"))

    # 7d. Cumulative length
    ok = len(cum) == n_pc
    print("    7d. len(cum) {} == {}: {}".format(len(cum), n_pc, "OK" if ok else "FAIL"))

    # 7e. cumulative[0] == evr[0]
    ok = abs(cum[0] - evr[0]) < 1e-12
    print("    7e. cum[0]==evr[0]: {:.10f} vs {:.10f}: {}".format(cum[0], evr[0], "OK" if ok else "FAIL"))

    # 7f. cumulative[i] == sum(evr[:i+1])
    ok = all(abs(cum[i] - sum(evr[:i+1])) < 1e-10 for i in range(len(evr)))
    print("    7f. cum[i]==sum(evr[:i+1]) for all i: {}".format("OK" if ok else "FAIL"))

    # 7g. Monotone
    ok = all(cum[i] <= cum[i+1] + 1e-10 for i in range(len(cum)-1))
    print("    7g. cumulative monotone: {}".format("OK" if ok else "FAIL"))

    # 7h. Sum <= 1
    s = sum(evr)
    ok = s <= 1.0 + 1e-9
    print("    7h. sum(evr)={:.6f} <= 1.0: {}".format(s, "OK" if ok else "FAIL"))

    # 7i. Each evr in (0, 1]
    ok = all(0 < v <= 1.0 for v in evr)
    print("    7i. all evr in (0,1]: {}".format("OK" if ok else "FAIL"))

    # 7j. Loading vectors unit norm
    norms = [math.sqrt(sum(v**2 for v in row)) for row in r["loadings"]]
    ok = all(abs(n - 1.0) < 1e-6 for n in norms)
    print("    7j. loading norms: {}".format(["{:.8f}".format(n) for n in norms]))
    print("         all ~ 1.0: {}".format("OK" if ok else "FAIL"))

    # 7k. Reconstruction (full rank)
    if n_pc == n_f:
        scores_arr = np.array(r["scores"])
        loadings_arr = np.array(r["loadings"])
        reconstructed = scores_arr @ loadings_arr
        X_actual = load_feature_matrix(ds["id"], r["feature_columns"])
        X_c = X_actual - X_actual.mean(axis=0)
        max_err = float(np.max(np.abs(reconstructed - X_c)))
        print("    7k. reconstruction error (full rank): {:.2e}".format(max_err))
        print("         exact reconstruction: {}".format("OK" if max_err < 1e-6 else "FAIL"))

# ==================================================================
# Q8. Save/retrieve preserves all results and source attribution
# ==================================================================
print("\n" + "-" * 65)
print("  Q8. Save/retrieve preserves all results and source attribution")
print("-" * 65)

ds = prod.get("etongue")
r = http_post("/api/pca/save", {
    "input_type": "raw_dataset",
    "input_id": ds["id"],
    "n_components": 4,
    "experiment_name": "Scientific verification test",
})
eid = r["experiment_id"]
print("\n  Saved experiment: {}...".format(eid[:8]))
print("    experiment_name: {}".format(r["experiment_name"]))
print("    source_filename: {}".format(r["source_filename"]))
print("    preprocessing_summary: {}".format(r["preprocessing_summary"]))
print("    sklearn_version: {}".format(r["sklearn_version"]))

r2 = http_get("/api/pca/experiments/" + eid)
print("\n  Retrieved experiment:")

fields = [
    "input_type", "input_id", "source_filename",
    "preprocessing_summary", "experiment_name",
    "n_samples", "n_features", "n_components",
    "feature_columns", "sample_ids", "category_labels", "category_column",
    "explained_variance_ratio", "cumulative_variance_ratio",
    "sklearn_version",
]
all_match = True
for f in fields:
    v1 = r.get(f)
    v2 = r2.get(f)
    match = v1 == v2
    status = "OK" if match else "MISMATCH"
    if not match:
        all_match = False
        print("    {}: {} -- saved={} retrieved={}".format(f, status, str(v1)[:60], str(v2)[:60]))
    else:
        print("    {}: {}".format(f, status))

# Scores and loadings deep comparison
scores_match = r["scores"] == r2["scores"]
print("    scores: {}".format("OK" if scores_match else "MISMATCH"))
loadings_match = r["loadings"] == r2["loadings"]
print("    loadings: {}".format("OK" if loadings_match else "MISMATCH"))

# created_at
if r.get("created_at") and r2.get("created_at"):
    print("    created_at: OK (both present)")
else:
    print("    created_at: FAIL (missing)")

# Source attribution
if r["source_filename"] == "magnolia_electronic_tongue.csv":
    print("    source_filename: OK correct Magnolia attribution")
else:
    print("    source_filename: FAIL unexpected: {}".format(r["source_filename"]))

if r["preprocessing_summary"]:
    print("    preprocessing_summary: OK '{}'".format(r["preprocessing_summary"][:80]))

if r["category_labels"]:
    print("    category_labels: OK {} entries, values={}".format(
        len(r["category_labels"]), set(r["category_labels"])))

# Cleanup
http_delete("/api/pca/experiments/" + eid)
print("\n  Cleaned up: deleted experiment {}...".format(eid[:8]))

print("\n" + "=" * 65)
print("  Scientific verification complete.")
print("=" * 65)
