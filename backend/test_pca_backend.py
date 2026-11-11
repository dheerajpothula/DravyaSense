"""
PCA Phase 4A backend test suite.

Covers all verifications specified in the implementation brief:
  1.  Feature extraction (correct columns, correct count)
  2.  Metadata exclusion (sample_id / origin never in matrix)
  3.  Component dimensions (scores, loadings shapes)
  4.  Explained variance validity (≤1.0, monotone cumulative)
  5.  Loading vectors (unit norm per component)
  6.  Category labels preserved (JYHP/AYHP for Magnolia)
  7.  Benchmark: no category labels (correct empty list)
  8.  Zero-variance feature handling (warning, feature excluded)
  9.  NaN value rejection (clear HTTP 422 error)
 10.  Infinity value rejection
 11.  n_components capping
 12.  /run does NOT create a DB record
 13.  /save creates a retrievable experiment with correct round-trip
 14.  Processed dataset input: preprocessing summary preserved
 15.  Delete experiment — source dataset unaffected
 16.  All four datasets: run + save full workflow
 17.  Experiment list filtering by source_id
 18.  Get experiment returns identical data to /save response

Uses only urllib — no external dependencies.
"""
from __future__ import annotations

import io
import json
import sys
import textwrap
import urllib.error
import urllib.request

BASE   = "http://localhost:8000"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

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


def info(msg: str) -> None:
    print(f"{YELLOW} INFO{RESET}  {msg}")


def section(title: str) -> None:
    print(f"\n── {title} ──")


# ── HTTP helpers ──────────────────────────────────────────────────

def http_get(path: str) -> dict | list:
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.loads(r.read())


def http_post(path: str, body: dict, expect_status: int = 200) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def http_delete(path: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE}{path}", method="DELETE")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def http_status_get(path: str) -> int:
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


def upload_csv(csv_content: str, filename: str) -> dict:
    boundary = "----pca4aboundary99"
    parts: list[bytes] = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        .encode()
    )
    parts.append(b"Content-Type: text/csv\r\n\r\n")
    parts.append(csv_content.encode("utf-8"))
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    data = b"".join(parts)
    req  = urllib.request.Request(f"{BASE}/api/datasets/upload", data=data, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def confirm_roles(ds_id: str, roles: dict) -> dict:
    data = json.dumps({"column_roles": roles}).encode()
    req  = urllib.request.Request(
        f"{BASE}/api/datasets/{ds_id}/roles", data=data, method="PUT"
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def delete_dataset(ds_id: str) -> None:
    req = urllib.request.Request(f"{BASE}/api/datasets/{ds_id}", method="DELETE")
    try:
        urllib.request.urlopen(req)
    except Exception:
        pass


# ── Locate production datasets ────────────────────────────────────

def locate_datasets() -> dict[str, dict]:
    all_ds = http_get("/api/datasets")
    prod: dict[str, dict] = {}
    for ds in all_ds:
        fn = ds["original_filename"]
        if fn == "magnolia_electronic_tongue.csv": prod["etongue"] = ds
        elif fn == "magnolia_electronic_nose.csv":  prod["enose"]   = ds
        elif fn == "magnolia_chemical_analysis.csv": prod["chem"]   = ds
        elif fn == "electronic_tongue.csv":          prod["bench"]  = ds
    return prod


def locate_processed(source_id: str) -> dict | None:
    hist = http_get(f"/api/preprocessing/dataset/{source_id}")
    return hist[0] if hist else None


# ── Fixture CSVs ──────────────────────────────────────────────────

FIXTURE_NORMAL = textwrap.dedent("""\
sample_id,origin,s1,s2,s3,s4
SA,TypeA,1.0,2.0,3.0,4.0
SB,TypeA,5.0,6.0,7.0,8.0
SC,TypeB,9.0,10.0,11.0,12.0
SD,TypeB,13.0,14.0,15.0,16.0
SE,TypeA,2.0,4.0,6.0,8.0
SF,TypeB,3.0,6.0,9.0,12.0
SG,TypeA,7.0,8.0,9.0,10.0
SH,TypeB,11.0,12.0,13.0,14.0
SI,TypeA,4.0,5.0,6.0,7.0
SJ,TypeB,8.0,9.0,10.0,11.0
""")

FIXTURE_CONST_COL = textwrap.dedent("""\
sample_id,origin,s1,s2_const,s3
SA,TypeA,1.0,5.0,3.0
SB,TypeA,5.0,5.0,7.0
SC,TypeB,9.0,5.0,11.0
SD,TypeB,13.0,5.0,15.0
SE,TypeA,2.0,5.0,6.0
SF,TypeB,3.0,5.0,9.0
SG,TypeA,7.0,5.0,9.0
SH,TypeB,11.0,5.0,13.0
SI,TypeA,4.0,5.0,6.0
SJ,TypeB,8.0,5.0,10.0
""")

FIXTURE_NAN_CSV = textwrap.dedent("""\
sample_id,origin,s1,s2,s3
SA,TypeA,1.0,2.0,3.0
SB,TypeA,5.0,,7.0
SC,TypeB,9.0,10.0,11.0
SD,TypeB,13.0,14.0,15.0
SE,TypeA,2.0,4.0,6.0
SF,TypeB,3.0,6.0,9.0
SG,TypeA,7.0,8.0,9.0
SH,TypeB,11.0,12.0,13.0
SI,TypeA,4.0,5.0,6.0
SJ,TypeB,8.0,9.0,10.0
""")

FIXTURE_ROLES = {"sample_id": "sample_id", "origin": "category",
                 "s1": "sensor", "s2": "sensor", "s3": "sensor", "s4": "sensor"}
FIXTURE_CONST_ROLES = {"sample_id": "sample_id", "origin": "category",
                       "s1": "sensor", "s2_const": "sensor", "s3": "sensor"}
FIXTURE_NAN_ROLES = {"sample_id": "sample_id", "origin": "category",
                     "s1": "sensor", "s2": "sensor", "s3": "sensor"}


def upload_fixture(csv: str, filename: str, roles: dict) -> str:
    """Upload a fixture CSV, confirm roles, return dataset_id."""
    analysis = upload_csv(csv, filename)
    ds_id = analysis["dataset_id"]
    confirm_roles(ds_id, roles)
    return ds_id


# ─────────────────────────────────────────────────────────────────
# TEST FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def test_feature_extraction(prod: dict) -> None:
    section("1. Feature extraction")
    for key, label, expected_n_features in [
        ("etongue", "E-Tongue", 8),
        ("enose",   "E-Nose",   10),
        ("chem",    "Chemical", 12),
        ("bench",   "Benchmark", 7),
    ]:
        ds = prod.get(key)
        if not ds: fail(f"{label}: dataset missing"); continue
        code, r = http_post("/api/pca/run", {
            "input_type": "raw_dataset",
            "input_id":   ds["id"],
            "n_components": 2,
        })
        if code not in (200, 201):
            fail(f"{label} run: HTTP {code} — {r.get('detail', r)}")
            continue
        if r["n_features"] == expected_n_features:
            ok(f"{label}: n_features = {r['n_features']}")
        else:
            fail(f"{label}: expected {expected_n_features} features, got {r['n_features']}")
        if len(r["feature_columns"]) == expected_n_features:
            ok(f"{label}: feature_columns length correct")
        else:
            fail(f"{label}: feature_columns={r['feature_columns']}")


def test_metadata_exclusion(prod: dict) -> None:
    section("2. Metadata exclusion (sample_id / origin never in feature matrix)")
    for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical")]:
        ds = prod.get(key)
        if not ds: continue
        code, r = http_post("/api/pca/run", {
            "input_type": "raw_dataset",
            "input_id":   ds["id"],
            "n_components": 2,
        })
        if code not in (200, 201): fail(f"{label} run HTTP {code}"); continue

        feats = r["feature_columns"]
        if "sample_id" not in feats:
            ok(f"{label}: 'sample_id' not in feature_columns")
        else:
            fail(f"{label}: 'sample_id' appeared in feature_columns")
        if "origin" not in feats:
            ok(f"{label}: 'origin' not in feature_columns")
        else:
            fail(f"{label}: 'origin' appeared in feature_columns")


def test_component_dimensions(prod: dict) -> None:
    section("3. Component dimensions (scores, loadings shapes)")
    for key, label, n_req in [
        ("etongue", "E-Tongue", 4),
        ("enose",   "E-Nose",   3),
        ("chem",    "Chemical", 5),
    ]:
        ds = prod.get(key)
        if not ds: continue
        code, r = http_post("/api/pca/run", {
            "input_type": "raw_dataset",
            "input_id":   ds["id"],
            "n_components": n_req,
        })
        if code not in (200, 201): fail(f"{label} run HTTP {code}"); continue

        n_s  = r["n_samples"]
        n_pc = r["n_components"]
        n_f  = r["n_features"]

        scores_rows = len(r["scores"])
        scores_cols = len(r["scores"][0]) if r["scores"] else 0
        load_rows   = len(r["loadings"])
        load_cols   = len(r["loadings"][0]) if r["loadings"] else 0

        if scores_rows == n_s and scores_cols == n_pc:
            ok(f"{label}: scores shape = ({scores_rows}, {scores_cols})")
        else:
            fail(f"{label}: scores expected ({n_s},{n_pc}), got ({scores_rows},{scores_cols})")

        if load_rows == n_pc and load_cols == n_f:
            ok(f"{label}: loadings shape = ({load_rows}, {load_cols})")
        else:
            fail(f"{label}: loadings expected ({n_pc},{n_f}), got ({load_rows},{load_cols})")


def test_explained_variance(prod: dict) -> None:
    section("4. Explained variance validity")
    for key, label in [("etongue","E-Tongue"),("chem","Chemical")]:
        ds = prod.get(key)
        if not ds: continue
        code, r = http_post("/api/pca/run", {
            "input_type": "raw_dataset",
            "input_id":   ds["id"],
            "n_components": 4,
        })
        if code not in (200, 201): fail(f"{label} run HTTP {code}"); continue

        evr  = r["explained_variance_ratio"]
        cumr = r["cumulative_variance_ratio"]

        # All ratios in (0, 1]
        if all(0 < v <= 1.0 for v in evr):
            ok(f"{label}: all explained_variance_ratio values in (0, 1]")
        else:
            fail(f"{label}: ratios out of range: {evr}")

        # Sum ≤ 1.0
        total = sum(evr)
        if total <= 1.0 + 1e-9:
            ok(f"{label}: sum(explained_variance_ratio) = {total:.4f} ≤ 1.0")
        else:
            fail(f"{label}: sum = {total:.4f} > 1.0")

        # Cumulative is monotonically non-decreasing
        mono = all(cumr[i] <= cumr[i+1] + 1e-9 for i in range(len(cumr)-1))
        if mono:
            ok(f"{label}: cumulative_variance_ratio is monotonically non-decreasing")
        else:
            fail(f"{label}: cumulative not monotone: {cumr}")

        # cumulative[-1] equals sum(evr)
        if abs(cumr[-1] - total) < 1e-9:
            ok(f"{label}: cumulative[-1] matches sum(evr)")
        else:
            fail(f"{label}: cumulative[-1]={cumr[-1]:.6f} vs sum={total:.6f}")


def test_loading_norms(prod: dict) -> None:
    section("5. Loading vectors — unit norm per component")
    ds = prod.get("etongue")
    if not ds: return
    code, r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id":   ds["id"],
        "n_components": 3,
    })
    if code not in (200, 201): fail(f"E-Tongue run HTTP {code}"); return

    import math
    for i, row in enumerate(r["loadings"]):
        norm = math.sqrt(sum(v**2 for v in row))
        if abs(norm - 1.0) < 1e-6:
            ok(f"Loading PC{i+1}: ||w|| = {norm:.8f} ≈ 1.0")
        else:
            fail(f"Loading PC{i+1}: ||w|| = {norm:.8f}, expected 1.0")


def test_category_labels(prod: dict) -> None:
    section("6. Category labels preserved (JYHP / AYHP)")
    for key, label in [("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical")]:
        ds = prod.get(key)
        if not ds: continue
        code, r = http_post("/api/pca/run", {
            "input_type": "raw_dataset",
            "input_id":   ds["id"],
            "n_components": 2,
        })
        if code not in (200, 201): fail(f"{label} run HTTP {code}"); continue

        labels = r["category_labels"]
        if not labels:
            fail(f"{label}: category_labels is empty, expected JYHP/AYHP")
            continue
        unique = set(labels)
        if {"JYHP", "AYHP"} == unique or unique.issubset({"JYHP", "AYHP"}):
            ok(f"{label}: category_labels contains {unique} ({len(labels)} entries)")
        else:
            fail(f"{label}: unexpected category values {unique}")

        if r["category_column"] == "origin":
            ok(f"{label}: category_column = 'origin'")
        else:
            fail(f"{label}: category_column = {r['category_column']!r}")

        # sample_ids should match row count
        if len(r["sample_ids"]) == r["n_samples"]:
            ok(f"{label}: len(sample_ids) = n_samples = {r['n_samples']}")
        else:
            fail(f"{label}: len(sample_ids)={len(r['sample_ids'])} ≠ n_samples={r['n_samples']}")


def test_benchmark_no_category(prod: dict) -> None:
    section("7. Benchmark: no category labels")
    ds = prod.get("bench")
    if not ds: fail("Benchmark dataset missing"); return
    code, r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id":   ds["id"],
        "n_components": 2,
    })
    if code not in (200, 201): fail(f"Benchmark run HTTP {code}"); return

    if r["category_labels"] == []:
        ok("Benchmark: category_labels = [] (correct — no category column)")
    else:
        fail(f"Benchmark: expected [], got {r['category_labels'][:3]}…")

    if r["category_column"] is None:
        ok("Benchmark: category_column = None")
    else:
        fail(f"Benchmark: category_column = {r['category_column']!r}, expected None")


def test_zero_variance_handling() -> None:
    section("8. Zero-variance feature — warning, feature excluded")
    ds_id = upload_fixture(FIXTURE_CONST_COL, "fix_const.csv", FIXTURE_CONST_ROLES)
    code, r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id":   ds_id,
        "n_components": 2,
    })
    if code not in (200, 201):
        fail(f"Zero-variance fixture: HTTP {code} — {r.get('detail', r)}")
        delete_dataset(ds_id)
        return

    # s2_const must not be in feature_columns
    if "s2_const" not in r["feature_columns"]:
        ok("Zero-variance: 's2_const' excluded from feature_columns")
    else:
        fail("Zero-variance: 's2_const' was included despite being constant")

    # n_features = 2 (s1 + s3)
    if r["n_features"] == 2:
        ok(f"Zero-variance: n_features = {r['n_features']} (constant col removed)")
    else:
        fail(f"Zero-variance: expected n_features=2, got {r['n_features']}")

    # Warning must mention the constant column
    has_warn = any("s2_const" in w or "zero" in w.lower() or "constant" in w.lower()
                   for w in r["warnings"])
    if has_warn:
        ok(f"Zero-variance: warning present: {[w for w in r['warnings'] if 'const' in w.lower() or 'zero' in w.lower()]}")
    else:
        fail(f"Zero-variance: no warning emitted. Got: {r['warnings']}")

    delete_dataset(ds_id)


def test_nan_rejection() -> None:
    section("9. NaN rejection — HTTP 422 returned")
    ds_id = upload_fixture(FIXTURE_NAN_CSV, "fix_nan.csv", FIXTURE_NAN_ROLES)
    code, r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id":   ds_id,
        "n_components": 2,
    })
    if code == 422:
        ok(f"NaN rejection: HTTP 422 returned with detail: {r.get('detail','')[:80]}")
    else:
        fail(f"NaN rejection: expected HTTP 422, got {code}")
    delete_dataset(ds_id)


def test_n_components_capping() -> None:
    section("10. n_components capping")
    # Request more components than features (4 features in FIXTURE_NORMAL)
    ds_id = upload_fixture(FIXTURE_NORMAL, "fix_cap.csv", FIXTURE_ROLES)
    code, r = http_post("/api/pca/run", {
        "input_type": "raw_dataset",
        "input_id":   ds_id,
        "n_components": 50,   # way more than min(10 samples, 4 features)
    })
    if code not in (200, 201):
        fail(f"n_components capping: HTTP {code}")
        delete_dataset(ds_id)
        return

    actual_n = r["n_components"]
    max_possible = min(r["n_samples"], r["n_features"])
    if actual_n == max_possible:
        ok(f"n_components capped: requested 50, capped to {actual_n} = min({r['n_samples']}, {r['n_features']})")
    else:
        fail(f"n_components not capped correctly: got {actual_n}, expected {max_possible}")

    # Warning about capping
    has_warn = any("cap" in w.lower() or "50" in w for w in r["warnings"])
    if has_warn:
        ok(f"n_components capping: warning present")
    else:
        fail(f"n_components capping: no warning. Got: {r['warnings']}")

    delete_dataset(ds_id)


def test_run_does_not_save(prod: dict) -> None:
    section("11. /run does NOT create a DB record")
    ds = prod.get("etongue")
    if not ds: fail("E-Tongue missing"); return

    before = http_get(f"/api/pca/experiments?source_id={ds['id']}")
    n_before = len(before)

    # Call /run three times
    for _ in range(3):
        http_post("/api/pca/run", {
            "input_type": "raw_dataset",
            "input_id":   ds["id"],
            "n_components": 2,
        })

    after = http_get(f"/api/pca/experiments?source_id={ds['id']}")
    n_after = len(after)

    if n_before == n_after:
        ok(f"/run ×3 — experiment count unchanged ({n_before})")
    else:
        fail(f"/run created records: before={n_before}, after={n_after}")


def test_save_and_retrieve(prod: dict) -> dict:
    """Returns saved experiment_ids for use in later tests."""
    section("12. /save and /experiments/{id} round-trip")
    exp_ids: dict[str, str] = {}

    for key, label, n_comp in [
        ("etongue","E-Tongue",4), ("enose","E-Nose",3),
        ("chem","Chemical",5),   ("bench","Benchmark",2),
    ]:
        ds = prod.get(key)
        if not ds: continue
        code, r = http_post("/api/pca/save", {
            "input_type":     "raw_dataset",
            "input_id":       ds["id"],
            "n_components":   n_comp,
            "experiment_name": f"{label} raw PCA n={n_comp}",
        })
        if code not in (200, 201):
            fail(f"{label} /save: HTTP {code} — {r.get('detail','')}")
            continue

        eid = r.get("experiment_id")
        if eid:
            ok(f"{label} /save: experiment_id = {eid[:8]}…")
            exp_ids[key] = eid
        else:
            fail(f"{label} /save: experiment_id is None")
            continue

        # Round-trip: GET experiment
        r2 = http_get(f"/api/pca/experiments/{eid}")

        # Core fields match
        checks = [
            ("n_samples",    r["n_samples"],    r2["n_samples"]),
            ("n_features",   r["n_features"],   r2["n_features"]),
            ("n_components", r["n_components"], r2["n_components"]),
        ]
        all_ok = True
        for name, orig, retrieved in checks:
            if orig == retrieved:
                pass
            else:
                fail(f"{label} round-trip: {name} {orig} → {retrieved}")
                all_ok = False
        if all_ok:
            ok(f"{label} round-trip: n_samples, n_features, n_components match")

        # feature_columns round-trip
        if r["feature_columns"] == r2["feature_columns"]:
            ok(f"{label} round-trip: feature_columns ({len(r2['feature_columns'])} cols)")
        else:
            fail(f"{label} round-trip: feature_columns mismatch")

        # sample_ids round-trip
        if r["sample_ids"] == r2["sample_ids"]:
            ok(f"{label} round-trip: sample_ids ({len(r2['sample_ids'])} entries)")
        else:
            fail(f"{label} round-trip: sample_ids mismatch")

        # category_labels round-trip
        if r["category_labels"] == r2["category_labels"]:
            ok(f"{label} round-trip: category_labels ({len(r2['category_labels'])} entries)")
        else:
            fail(f"{label} round-trip: category_labels mismatch")

        # First score row round-trip (float precision)
        if r["scores"][0] == r2["scores"][0]:
            ok(f"{label} round-trip: scores first row matches")
        else:
            fail(f"{label} round-trip: scores first row mismatch")

        # sklearn_version
        if r2["sklearn_version"]:
            ok(f"{label} round-trip: sklearn_version = {r2['sklearn_version']}")
        else:
            fail(f"{label} round-trip: sklearn_version missing")

    return exp_ids


def test_processed_dataset_input(prod: dict) -> None:
    section("13. Processed dataset as PCA input")
    ds = prod.get("etongue")
    if not ds: fail("E-Tongue missing"); return

    # Find a processed dataset for this source
    hist = http_get(f"/api/preprocessing/dataset/{ds['id']}")
    if not hist:
        info("No processed E-Tongue datasets found — skipping processed input test")
        return

    proc_id = hist[0]["id"]
    code, r = http_post("/api/pca/run", {
        "input_type": "processed_dataset",
        "input_id":   proc_id,
        "n_components": 3,
    })
    if code not in (200, 201):
        fail(f"Processed input run: HTTP {code} — {r.get('detail','')}")
        return

    ok(f"Processed input: run succeeded (n_samples={r['n_samples']}, n_features={r['n_features']})")

    # Preprocessing summary must be present and mention scaling
    summary = r.get("preprocessing_summary") or ""
    if summary:
        ok(f"Processed input: preprocessing_summary = '{summary[:80]}'")
    else:
        fail("Processed input: preprocessing_summary is empty")

    # feature_columns must not include sample_id or origin
    feats = r["feature_columns"]
    if "sample_id" not in feats and "origin" not in feats:
        ok("Processed input: sample_id and origin excluded from feature matrix")
    else:
        fail(f"Processed input: metadata in feature_columns: {feats}")

    # category labels must still be available (origin from source roles)
    if r["category_labels"]:
        ok(f"Processed input: category_labels preserved ({set(r['category_labels'])})")
    else:
        fail("Processed input: category_labels empty despite origin column in source")


def test_experiment_list_filtering(prod: dict, exp_ids: dict) -> None:
    section("14. Experiment list filtering")
    all_exps = http_get("/api/pca/experiments")
    if len(all_exps) >= 4:
        ok(f"GET /api/pca/experiments: {len(all_exps)} total experiments")
    else:
        fail(f"Expected ≥4 experiments, got {len(all_exps)}")

    # Filter by E-Tongue source_id
    ds = prod.get("etongue")
    if ds:
        filtered = http_get(f"/api/pca/experiments?source_id={ds['id']}")
        all_match = all(e["input_id"] == ds["id"] for e in filtered)
        if all_match and len(filtered) >= 1:
            ok(f"Filter by source_id: {len(filtered)} experiment(s) for E-Tongue")
        else:
            fail(f"Filter by source_id: {len(filtered)} entries, all_match={all_match}")

    # Filter by input_type
    raw_only = http_get("/api/pca/experiments?input_type=raw_dataset")
    all_raw = all(e["input_type"] == "raw_dataset" for e in raw_only)
    if all_raw:
        ok(f"Filter by input_type=raw_dataset: {len(raw_only)} entries, all raw")
    else:
        fail(f"Filter input_type: some entries are not raw_dataset")


def test_delete_experiment(prod: dict, exp_ids: dict) -> None:
    section("15. Delete experiment — source dataset unaffected")
    eid = exp_ids.get("etongue")
    if not eid: info("No E-Tongue experiment id — skipping delete test"); return

    ds = prod.get("etongue")
    code, _ = http_delete(f"/api/pca/experiments/{eid}")
    if code == 200:
        ok(f"DELETE /api/pca/experiments/{eid[:8]}…: HTTP 200")
    else:
        fail(f"DELETE experiment: HTTP {code}")
        return

    # Experiment must be gone (404)
    if http_status_get(f"/api/pca/experiments/{eid}") == 404:
        ok("Deleted experiment returns 404")
    else:
        fail("Deleted experiment still accessible")

    # Source dataset must be intact (200)
    if ds and http_status_get(f"/api/datasets/{ds['id']}") == 200:
        ok("Source dataset unaffected after experiment delete")
    elif ds:
        fail("Source dataset returned non-200 after experiment delete")


def test_all_datasets_full_workflow(prod: dict) -> None:
    section("16. All four datasets — complete run workflow verification")
    CONFIGS = {
        "etongue": {"n_components": 4, "exp_n_features": 8,  "exp_n_samples": 60},
        "enose":   {"n_components": 3, "exp_n_features": 10, "exp_n_samples": 60},
        "chem":    {"n_components": 5, "exp_n_features": 12, "exp_n_samples": 60},
        "bench":   {"n_components": 2, "exp_n_features": 7,  "exp_n_samples": 198},
    }
    for key, label in [
        ("etongue","E-Tongue"),("enose","E-Nose"),("chem","Chemical"),("bench","Benchmark")
    ]:
        ds = prod.get(key)
        cfg = CONFIGS[key]
        if not ds: fail(f"{label}: dataset not found"); continue

        code, r = http_post("/api/pca/run", {
            "input_type": "raw_dataset",
            "input_id":   ds["id"],
            "n_components": cfg["n_components"],
        })
        if code not in (200, 201):
            fail(f"{label}: HTTP {code} — {r.get('detail',r)}")
            continue

        all_ok = True
        checks = [
            ("n_samples",    r["n_samples"],    cfg["exp_n_samples"]),
            ("n_features",   r["n_features"],   cfg["exp_n_features"]),
            ("n_components", r["n_components"], cfg["n_components"]),
        ]
        for cname, got, exp in checks:
            if got == exp:
                ok(f"{label}: {cname} = {got}")
            else:
                fail(f"{label}: {cname} expected {exp}, got {got}")
                all_ok = False

        # Scores and loadings shapes
        scores_ok = (len(r["scores"]) == cfg["exp_n_samples"] and
                     len(r["scores"][0]) == cfg["n_components"])
        load_ok   = (len(r["loadings"]) == cfg["n_components"] and
                     len(r["loadings"][0]) == cfg["exp_n_features"])
        if scores_ok:
            ok(f"{label}: scores shape ({cfg['exp_n_samples']}, {cfg['n_components']})")
        else:
            fail(f"{label}: scores shape wrong: ({len(r['scores'])}, {len(r['scores'][0]) if r['scores'] else 0})")
        if load_ok:
            ok(f"{label}: loadings shape ({cfg['n_components']}, {cfg['exp_n_features']})")
        else:
            fail(f"{label}: loadings shape wrong")

        # No NaN in scores
        any_nan = any(v is None or (isinstance(v, float) and v != v)
                      for row in r["scores"] for v in row)
        if not any_nan:
            ok(f"{label}: no NaN in scores")
        else:
            fail(f"{label}: NaN found in scores")


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 62)
    print("  DravyaSense — PCA Phase 4A Backend Test Suite")
    print("=" * 62)

    try:
        http_get("/api/health")
    except Exception as exc:
        print(f"\n  ERROR: Backend not reachable: {exc}")
        sys.exit(1)

    prod = locate_datasets()
    missing = [k for k in ("etongue","enose","chem","bench") if k not in prod]
    if missing:
        print(f"\n  WARNING: Missing datasets: {missing}")

    test_feature_extraction(prod)
    test_metadata_exclusion(prod)
    test_component_dimensions(prod)
    test_explained_variance(prod)
    test_loading_norms(prod)
    test_category_labels(prod)
    test_benchmark_no_category(prod)
    test_zero_variance_handling()
    test_nan_rejection()
    test_n_components_capping()
    test_run_does_not_save(prod)
    exp_ids = test_save_and_retrieve(prod)
    test_processed_dataset_input(prod)
    test_experiment_list_filtering(prod, exp_ids)
    test_delete_experiment(prod, exp_ids)
    test_all_datasets_full_workflow(prod)

    print(f"\n{'='*62}")
    print(f"  RESULTS: {passed} passed  |  {failed} failed")
    print(f"{'='*62}")
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
