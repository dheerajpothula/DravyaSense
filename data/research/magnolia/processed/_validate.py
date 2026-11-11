"""
Validation script for the three Magnolia research CSV files.
Run from the repo root: python data/research/magnolia/processed/_validate.py
"""
import pandas as pd
import pathlib

BASE = pathlib.Path(__file__).parent

files = {
    "Electronic Tongue": BASE / "magnolia_electronic_tongue.csv",
    "Electronic Nose":   BASE / "magnolia_electronic_nose.csv",
    "Chemical Analysis": BASE / "magnolia_chemical_analysis.csv",
}

dfs = {}
all_ok = True

for name, path in files.items():
    df = pd.read_csv(path)
    dfs[name] = df
    print(f"=== {name} ===")

    # 1. Row count
    rc = len(df)
    ok1 = rc == 60
    mark = "OK" if ok1 else "FAIL"
    print(f"  [{mark}] Row count: {rc} (expected 60)")
    if not ok1:
        all_ok = False

    # 2. Unique sample IDs
    uid = df["sample_id"].nunique()
    ok2 = uid == 60
    mark = "OK" if ok2 else "FAIL"
    print(f"  [{mark}] Unique sample IDs: {uid} (expected 60)")
    if not ok2:
        all_ok = False

    # 3. Origin counts
    vc = df["origin"].value_counts()
    jyhp = int(vc.get("JYHP", 0))
    ayhp = int(vc.get("AYHP", 0))
    ok3 = jyhp == 30 and ayhp == 30
    mark = "OK" if ok3 else "FAIL"
    print(f"  [{mark}] Origins: JYHP={jyhp}, AYHP={ayhp} (expected 30 each)")
    if not ok3:
        all_ok = False

    # 4. Sample ID sequence S1..S60
    expected_ids = [f"S{i}" for i in range(1, 61)]
    actual_ids = df["sample_id"].tolist()
    ok4 = actual_ids == expected_ids
    mark = "OK" if ok4 else "FAIL"
    desc = "correct" if ok4 else "MISMATCH"
    print(f"  [{mark}] Sample ID sequence S1..S60: {desc}")
    if not ok4:
        all_ok = False

    # 5. Missing values
    total_missing = int(df.isna().sum().sum())
    ok5 = total_missing == 0
    mark = "OK" if ok5 else "FAIL"
    print(f"  [{mark}] Missing values: {total_missing}")
    if not ok5:
        all_ok = False

    # 6. Numeric column count
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    print(f"  [INFO] Numeric columns ({len(numeric_cols)}): {numeric_cols}")

    # 7. Negative values — expected only in e-tongue sourness/saltiness columns
    for col in numeric_cols:
        neg_count = int((df[col] < 0).sum())
        if neg_count > 0:
            print(f"  [INFO] Negative values in column '{col}': {neg_count} rows")

    print()

# 8. Cross-file sample ID alignment
print("=== Cross-file Sample ID Alignment ===")
ref_name = "Electronic Tongue"
ref_ids = set(dfs[ref_name]["sample_id"].tolist())
for name, df in dfs.items():
    id_set = set(df["sample_id"].tolist())
    ok = id_set == ref_ids
    mark = "OK" if ok else "FAIL"
    desc = "identical" if ok else "MISMATCH"
    print(f"  [{mark}] {name} vs {ref_name}: {desc}")
    if not ok:
        all_ok = False

# 9. Spot-check key values against supplementary PDF
print()
print("=== Spot-Check Against Supplementary PDF ===")
checks = [
    # (dataset_name, sample_id, column, expected_value, tolerance)
    ("Electronic Tongue", "S1",  "sourness_mV",                -24.60,  0.001),
    ("Electronic Tongue", "S1",  "bitterness_mV",               16.37,  0.001),
    ("Electronic Tongue", "S9",  "astringency_mV",               9.33,  0.001),
    ("Electronic Tongue", "S36", "bitterness_mV",               23.78,  0.001),
    ("Electronic Tongue", "S38", "umami_mV",                    10.51,  0.001),
    ("Electronic Tongue", "S60", "saltiness_mV",               -12.98,  0.001),
    ("Electronic Tongue", "S51", "richness_mV",                 -0.07,  0.001),
    ("Electronic Tongue", "S14", "richness_mV",                 -0.01,  0.001),
    ("Electronic Nose",   "S1",  "W5S",                         30.707, 0.001),
    ("Electronic Nose",   "S1",  "W1W",                         34.856, 0.001),
    ("Electronic Nose",   "S27", "W5S",                         45.615, 0.001),
    ("Electronic Nose",   "S27", "W3S",                          1.502, 0.001),
    ("Electronic Nose",   "S44", "W2S",                          0.982, 0.001),
    ("Electronic Nose",   "S60", "W1W",                         11.970, 0.001),
    ("Electronic Nose",   "S49", "W1C",                          1.061, 0.001),
    ("Chemical Analysis", "S1",  "magnoloside_B_mg_g",          44.494, 0.001),
    ("Chemical Analysis", "S1",  "THM_mg_g",                    47.974, 0.001),
    ("Chemical Analysis", "S18", "THM_mg_g",                    99.564, 0.001),
    ("Chemical Analysis", "S27", "piperitylmagnolol_mg_g",       0.000, 0.001),
    ("Chemical Analysis", "S27", "beta_eudesmol_mg_g",           0.000, 0.001),
    ("Chemical Analysis", "S16", "magnoloside_B_mg_g",          54.275, 0.001),
    ("Chemical Analysis", "S16", "magnoloside_A_mg_g",          12.326, 0.001),
    ("Chemical Analysis", "S53", "piperitylmagnolol_mg_g",       0.000, 0.001),
    ("Chemical Analysis", "S60", "PHM_ratio",                    1.149, 0.001),
    ("Chemical Analysis", "S60", "PBA_ratio",                    4.592, 0.001),
]

for ds_name, sid, col, expected, tol in checks:
    df = dfs[ds_name]
    actual = float(df.loc[df["sample_id"] == sid, col].values[0])
    ok = abs(actual - expected) <= tol
    mark = "OK" if ok else "FAIL"
    if not ok:
        all_ok = False
    print(f"  [{mark}] {ds_name} | {sid} | {col}: got {actual}, expected {expected}")

print()
result = "ALL CHECKS PASSED" if all_ok else "FAILURES DETECTED"
print(f"=== OVERALL RESULT: {result} ===")
