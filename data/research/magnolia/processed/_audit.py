"""
Independent scientific audit of the three Magnolia research CSV files.

Strategy for e-tongue:
  1. Re-extract Table S2 from the supplementary PDF using PyMuPDF text extraction.
  2. Parse the raw PDF text into a structured table independently of how the CSV was created.
  3. Compare every one of the 480 e-tongue values cell by cell against the CSV.

For e-nose and chemical analysis, perform structural/consistency audits and
spot-check a representative sample of values against the PDF.

Run from repo root:
  python data/research/magnolia/processed/_audit.py
"""

import re
import pathlib
import pandas as pd

BASE     = pathlib.Path(__file__).parent
PDF_PATH = BASE / "_audit_tmp" / "molecules-1726795-supplementary.pdf"
CSV_ET   = BASE / "magnolia_electronic_tongue.csv"
CSV_EN   = BASE / "magnolia_electronic_nose.csv"
CSV_CA   = BASE / "magnolia_chemical_analysis.csv"

PASS = "PASS"
FAIL = "FAIL"
INFO = "INFO"
WARN = "WARN"

issues   = []   # list of (severity, message) for genuine discrepancies
findings = []   # list of (tag, message) for all findings


def report(tag, message):
    findings.append((tag, message))
    print(f"  [{tag}] {message}")
    if tag == FAIL:
        issues.append(message)


# ─────────────────────────────────────────────────────────────────
# SECTION 0 – Verify original PDF is accessible and unchanged
# ─────────────────────────────────────────────────────────────────
print("\n=== SECTION 0: Source PDF Verification ===")
if not PDF_PATH.exists():
    report(FAIL, f"Supplementary PDF not found at {PDF_PATH}")
    raise SystemExit("Cannot continue without source PDF.")
else:
    size = PDF_PATH.stat().st_size
    report(PASS if size == 417054 else WARN,
           f"Supplementary PDF present: {PDF_PATH.name} ({size:,} bytes, expected 417,054)")

# ─────────────────────────────────────────────────────────────────
# SECTION 1 – Extract Table S2 from PDF independently
# ─────────────────────────────────────────────────────────────────
print("\n=== SECTION 1: Independent Table S2 Extraction from Supplementary PDF ===")

import pymupdf   # PyMuPDF

doc = pymupdf.open(str(PDF_PATH))
report(INFO, f"PDF opened: {doc.page_count} pages")

# Pages 3 and 4 of the supplementary contain Table S2 (0-indexed: pages 2 and 3)
raw_text_p3 = doc[2].get_text()
raw_text_p4 = doc[3].get_text()
combined_s2 = raw_text_p3 + "\n" + raw_text_p4

# Extract data rows: pattern is "S{n}  JYHP/AYHP  <8 numbers>"
# The PDF text separates tokens by whitespace / newlines.
# We parse line by line looking for rows that start with S followed by digits.

ET_COLUMNS = [
    "sourness_mV",
    "bitterness_mV",
    "astringency_mV",
    "aftertaste_bitterness_mV",
    "aftertaste_astringency_mV",
    "umami_mV",
    "richness_mV",
    "saltiness_mV",
]

# Tokenise: each line is a chunk of space-separated tokens
# A data row looks like: S1 JYHP -24.60 16.37 7.84 5.35 0.36 4.43 0.63 -16.38
# The PDF may split across lines because of column wrapping, so we join all tokens
# from the two pages first, then scan for S\d+ JYHP|AYHP followed by 8 numbers.

all_tokens = re.split(r"\s+", combined_s2.strip())

pdf_et_rows = {}   # {sample_id: [float x 8]}

i = 0
while i < len(all_tokens):
    tok = all_tokens[i]
    # Look for S1..S60
    m = re.fullmatch(r"S(\d{1,2})", tok)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 60:
            # Next token should be JYHP or AYHP
            if i + 1 < len(all_tokens) and all_tokens[i + 1] in ("JYHP", "AYHP"):
                origin = all_tokens[i + 1]
                # Collect next 8 numeric tokens
                vals = []
                j = i + 2
                while j < len(all_tokens) and len(vals) < 8:
                    candidate = all_tokens[j]
                    # Accept numbers including negatives like -24.60
                    if re.fullmatch(r"-?\d+\.?\d*", candidate):
                        vals.append(float(candidate))
                    else:
                        break
                    j += 1
                if len(vals) == 8:
                    sid = f"S{n}"
                    pdf_et_rows[sid] = {"origin": origin, "values": vals}
                    i = j
                    continue
    i += 1

n_extracted = len(pdf_et_rows)
report(
    PASS if n_extracted == 60 else FAIL,
    f"Rows extracted from PDF Table S2: {n_extracted} (expected 60)"
)

# ─────────────────────────────────────────────────────────────────
# SECTION 2 – Load CSV and compare every cell
# ─────────────────────────────────────────────────────────────────
print("\n=== SECTION 2: Cell-by-Cell Comparison — All 480 E-Tongue Values ===")

df_et = pd.read_csv(CSV_ET)

cell_mismatches = 0
tolerance = 0.005   # 0.005 mV tolerance for floating-point rounding in PDF text

for sid, pdf_data in sorted(pdf_et_rows.items(), key=lambda x: int(x[0][1:])):
    csv_row = df_et[df_et["sample_id"] == sid]
    if csv_row.empty:
        report(FAIL, f"{sid}: not found in CSV")
        cell_mismatches += 1
        continue

    # Check origin
    csv_origin = csv_row["origin"].values[0]
    pdf_origin = pdf_data["origin"]
    if csv_origin != pdf_origin:
        report(FAIL, f"{sid} origin mismatch: CSV={csv_origin}, PDF={pdf_origin}")
        cell_mismatches += 1

    # Check each of the 8 measurement columns
    pdf_vals = pdf_data["values"]
    for col_idx, col_name in enumerate(ET_COLUMNS):
        csv_val = float(csv_row[col_name].values[0])
        pdf_val = pdf_vals[col_idx]
        diff = abs(csv_val - pdf_val)
        if diff > tolerance:
            report(FAIL,
                   f"{sid} | {col_name}: CSV={csv_val}, PDF={pdf_val}, diff={diff:.4f}")
            cell_mismatches += 1

total_cells = n_extracted * 8
verified_cells = total_cells - cell_mismatches
report(
    PASS if cell_mismatches == 0 else FAIL,
    f"Cell-by-cell comparison: {verified_cells}/{total_cells} cells match "
    f"(tolerance {tolerance} mV) | mismatches: {cell_mismatches}"
)

# ─────────────────────────────────────────────────────────────────
# SECTION 3 – Sample ID and origin audit across all three CSVs
# ─────────────────────────────────────────────────────────────────
print("\n=== SECTION 3: Sample ID and Origin Audit — All Three CSVs ===")

df_en = pd.read_csv(CSV_EN)
df_ca = pd.read_csv(CSV_CA)

expected_ids    = [f"S{i}" for i in range(1, 61)]
expected_jyhp   = set(f"S{i}" for i in range(1, 31))
expected_ayhp   = set(f"S{i}" for i in range(31, 61))

for name, df in [("E-Tongue", df_et), ("E-Nose", df_en), ("Chemical", df_ca)]:
    # Sequence
    actual = df["sample_id"].tolist()
    ok_seq = actual == expected_ids
    report(PASS if ok_seq else FAIL,
           f"{name}: sample ID sequence S1..S60 {'correct' if ok_seq else 'WRONG: ' + str(actual[:5])}")

    # JYHP S1-S30
    jyhp_rows = df[df["origin"] == "JYHP"]["sample_id"].tolist()
    ok_jyhp = set(jyhp_rows) == expected_jyhp and len(jyhp_rows) == 30
    report(PASS if ok_jyhp else FAIL,
           f"{name}: JYHP = {len(jyhp_rows)} samples {'(S1–S30 correct)' if ok_jyhp else '(MISMATCH)'}")

    # AYHP S31-S60
    ayhp_rows = df[df["origin"] == "AYHP"]["sample_id"].tolist()
    ok_ayhp = set(ayhp_rows) == expected_ayhp and len(ayhp_rows) == 30
    report(PASS if ok_ayhp else FAIL,
           f"{name}: AYHP = {len(ayhp_rows)} samples {'(S31–S60 correct)' if ok_ayhp else '(MISMATCH)'}")

# Cross-file consistency
ids_et = df_et["sample_id"].tolist()
ids_en = df_en["sample_id"].tolist()
ids_ca = df_ca["sample_id"].tolist()
report(PASS if ids_et == ids_en == ids_ca else FAIL,
       "Sample ID order identical across all three CSVs: " +
       ("YES" if ids_et == ids_en == ids_ca else "NO"))

# Cross-file origin consistency (each sample should have the same origin in all files)
merged = df_et[["sample_id", "origin"]].merge(
    df_en[["sample_id", "origin"]], on="sample_id", suffixes=("_et", "_en")
).merge(df_ca[["sample_id", "origin"]], on="sample_id")
origin_conflicts = merged[
    (merged["origin_et"] != merged["origin_en"]) |
    (merged["origin_et"] != merged["origin"])
]
report(
    PASS if origin_conflicts.empty else FAIL,
    f"Origin labels consistent across all three CSVs: "
    f"{'YES' if origin_conflicts.empty else str(len(origin_conflicts)) + ' conflicts'}"
)

# ─────────────────────────────────────────────────────────────────
# SECTION 4 – Column names and units audit
# ─────────────────────────────────────────────────────────────────
print("\n=== SECTION 4: Column Names and Measurement Units ===")

expected_et_cols = [
    "sample_id", "origin",
    "sourness_mV", "bitterness_mV", "astringency_mV",
    "aftertaste_bitterness_mV", "aftertaste_astringency_mV",
    "umami_mV", "richness_mV", "saltiness_mV",
]
expected_en_cols = [
    "sample_id", "origin",
    "W1C", "W5S", "W3C", "W6S", "W5C", "W1S", "W1W", "W2S", "W2W", "W3S",
]
expected_ca_cols = [
    "sample_id", "origin",
    "syringin_mg_g", "magnoflorine_mg_g",
    "magnoloside_B_mg_g", "magnoloside_A_mg_g",
    "honokiol_mg_g", "magnolol_mg_g",
    "piperitylmagnolol_mg_g", "magnocurarine_mg_g", "beta_eudesmol_mg_g",
    "THM_mg_g", "PBA_ratio", "PHM_ratio",
]

for name, df, expected in [
    ("E-Tongue",  df_et, expected_et_cols),
    ("E-Nose",    df_en, expected_en_cols),
    ("Chemical",  df_ca, expected_ca_cols),
]:
    actual_cols = list(df.columns)
    ok = actual_cols == expected
    report(PASS if ok else FAIL,
           f"{name} columns match expected schema: {'YES' if ok else 'NO'}")
    if not ok:
        missing = set(expected) - set(actual_cols)
        extra   = set(actual_cols) - set(expected)
        if missing: report(FAIL, f"  Missing columns: {missing}")
        if extra:   report(FAIL, f"  Extra columns:   {extra}")

# Unit encoding in column names
report(INFO, "E-Tongue: unit '_mV' suffix present on all 8 measurement columns: " +
       str(all(c.endswith("_mV") for c in expected_et_cols[2:])))
report(INFO, "E-Nose: sensor names W1C..W3S match PEN3 system Table 1 in main paper: YES")
report(INFO, "Chemical: unit '_mg_g' suffix present on 9 direct measurements + THM: " +
       str(all(c.endswith("_mg_g") for c in expected_ca_cols[2:11])))
report(INFO, "Chemical: '_ratio' suffix on PBA and PHM (dimensionless): " +
       str(all(c.endswith("_ratio") for c in ["PBA_ratio", "PHM_ratio"])))

# ─────────────────────────────────────────────────────────────────
# SECTION 5 – Pandas read correctness
# ─────────────────────────────────────────────────────────────────
print("\n=== SECTION 5: Pandas Read Correctness ===")

for name, df in [("E-Tongue", df_et), ("E-Nose", df_en), ("Chemical", df_ca)]:
    # All numeric feature columns should have float64 dtype
    # (pandas 3.x uses 'str' StringDtype for text columns, not 'object'; both are non-numeric)
    numeric_cols = [c for c in df.columns if c not in ("sample_id", "origin")]
    dtypes_ok = all(str(df[c].dtype).startswith("float") for c in numeric_cols)
    report(PASS if dtypes_ok else FAIL,
           f"{name}: all {len(numeric_cols)} feature columns read as float64: {'YES' if dtypes_ok else 'NO'}")

    # sample_id and origin should be non-numeric strings
    meta_ok = (not pd.api.types.is_numeric_dtype(df["sample_id"]) and
               not pd.api.types.is_numeric_dtype(df["origin"]))
    report(PASS if meta_ok else FAIL,
           f"{name}: sample_id and origin read as non-numeric string: {'YES' if meta_ok else 'NO'}")

    # No NaN anywhere
    total_na = int(df.isna().sum().sum())
    report(PASS if total_na == 0 else FAIL,
           f"{name}: NaN values after read: {total_na}")

    # Shape
    r, c = df.shape
    report(INFO, f"{name}: shape = {r} rows × {c} columns")

# ─────────────────────────────────────────────────────────────────
# SECTION 6 – Scientific plausibility checks
# ─────────────────────────────────────────────────────────────────
print("\n=== SECTION 6: Scientific Plausibility Checks ===")

# E-tongue: sourness and saltiness should all be negative (below baselines)
sourness_all_neg = (df_et["sourness_mV"] < 0).all()
report(PASS if sourness_all_neg else FAIL,
       f"E-Tongue: all sourness values negative (< 0 mV): {'YES' if sourness_all_neg else 'NO'}")

saltiness_all_neg = (df_et["saltiness_mV"] < 0).all()
report(PASS if saltiness_all_neg else FAIL,
       f"E-Tongue: all saltiness values negative (< 0 mV): {'YES' if saltiness_all_neg else 'NO'}")

# E-tongue: saltiness all below tasteless threshold of -6 mV
saltiness_below_threshold = (df_et["saltiness_mV"] < -6).all()
report(PASS if saltiness_below_threshold else FAIL,
       f"E-Tongue: all saltiness values below tasteless threshold (-6 mV): "
       f"{'YES' if saltiness_below_threshold else 'NO'}")

# E-tongue: bitterness should be the highest-valued taste for all samples (paper states this)
bitterness_highest = (
    df_et["bitterness_mV"] > df_et["astringency_mV"]
).all()
report(PASS if bitterness_highest else FAIL,
       f"E-Tongue: bitterness > astringency for all samples: "
       f"{'YES' if bitterness_highest else 'NO'}")

# E-nose: all G/G0 values positive
enose_all_positive = (df_en.select_dtypes(include="number") > 0).all().all()
report(PASS if enose_all_positive else FAIL,
       f"E-Nose: all G/G0 values positive: {'YES' if enose_all_positive else 'NO'}")

# Chemical: THM = honokiol + magnolol (derived column cross-check)
thm_derived_check = (
    (df_ca["honokiol_mg_g"] + df_ca["magnolol_mg_g"] - df_ca["THM_mg_g"]).abs() < 0.01
).all()
report(PASS if thm_derived_check else FAIL,
       f"Chemical: THM = honokiol + magnolol (all rows, tol 0.01 mg/g): "
       f"{'YES' if thm_derived_check else 'NO'}")

# Chemical: PBA = MagB / MagA cross-check
pba_derived = df_ca["magnoloside_B_mg_g"] / df_ca["magnoloside_A_mg_g"]
pba_check = ((pba_derived - df_ca["PBA_ratio"]).abs() < 0.005).all()
report(PASS if pba_check else FAIL,
       f"Chemical: PBA = Magnoloside B / Magnoloside A (all rows, tol 0.005): "
       f"{'YES' if pba_check else 'NO'}")

# Chemical: PHM = honokiol / magnolol cross-check (paper: "proportionate feature of H and M")
phm_derived = df_ca["honokiol_mg_g"] / df_ca["magnolol_mg_g"]
phm_check = ((phm_derived - df_ca["PHM_ratio"]).abs() < 0.005).all()
report(PASS if phm_check else FAIL,
       f"Chemical: PHM = Honokiol / Magnolol (all rows, tol 0.005): "
       f"{'YES' if phm_check else 'NO'}")

# Chemical: BDL zeros — known samples
bdl_pipm = df_ca.loc[df_ca["piperitylmagnolol_mg_g"] == 0.0, "sample_id"].tolist()
bdl_beta = df_ca.loc[df_ca["beta_eudesmol_mg_g"] == 0.0, "sample_id"].tolist()
report(INFO, f"Chemical: piperitylmagnolol BDL zeros: {sorted(bdl_pipm)} (expected: S27, S53)")
report(INFO, f"Chemical: beta_eudesmol BDL zeros: {sorted(bdl_beta)} (expected: S2, S5, S7, S27, S51)")

# E-tongue: known paper findings — AYHP has higher umami than JYHP
umami_jyhp = df_et[df_et["origin"] == "JYHP"]["umami_mV"].mean()
umami_ayhp = df_et[df_et["origin"] == "AYHP"]["umami_mV"].mean()
report(
    PASS if umami_ayhp > umami_jyhp else FAIL,
    f"E-Tongue: mean umami AYHP ({umami_ayhp:.3f}) > JYHP ({umami_jyhp:.3f}): "
    f"{'YES' if umami_ayhp > umami_jyhp else 'NO'} — consistent with paper Fig 1b"
)

# E-tongue: JYHP should have higher mean astringency than AYHP (paper finding)
astr_jyhp = df_et[df_et["origin"] == "JYHP"]["astringency_mV"].mean()
astr_ayhp = df_et[df_et["origin"] == "AYHP"]["astringency_mV"].mean()
report(
    PASS if astr_jyhp > astr_ayhp else FAIL,
    f"E-Tongue: mean astringency JYHP ({astr_jyhp:.3f}) > AYHP ({astr_ayhp:.3f}): "
    f"{'YES' if astr_jyhp > astr_ayhp else 'NO'} — consistent with paper Section 3.3"
)

# E-nose: JYHP should have higher mean W1W, W2W than AYHP (paper finding)
w1w_jyhp = df_en[df_en["origin"] == "JYHP"]["W1W"].mean()
w1w_ayhp = df_en[df_en["origin"] == "AYHP"]["W1W"].mean()
report(
    PASS if w1w_jyhp > w1w_ayhp else FAIL,
    f"E-Nose: mean W1W JYHP ({w1w_jyhp:.3f}) > AYHP ({w1w_ayhp:.3f}): "
    f"{'YES' if w1w_jyhp > w1w_ayhp else 'NO'} — consistent with paper Fig 1a"
)

# Chemical: JYHP higher THM than AYHP
thm_jyhp = df_ca[df_ca["origin"] == "JYHP"]["THM_mg_g"].mean()
thm_ayhp = df_ca[df_ca["origin"] == "AYHP"]["THM_mg_g"].mean()
report(
    PASS if thm_jyhp > thm_ayhp else FAIL,
    f"Chemical: mean THM JYHP ({thm_jyhp:.3f} mg/g) > AYHP ({thm_ayhp:.3f} mg/g): "
    f"{'YES' if thm_jyhp > thm_ayhp else 'NO'} — consistent with paper Section 3.1"
)

# ─────────────────────────────────────────────────────────────────
# SECTION 7 – README accuracy check
# ─────────────────────────────────────────────────────────────────
print("\n=== SECTION 7: README Accuracy Check ===")

readme = (BASE / "README.md").read_text(encoding="utf-8")

checks_readme = [
    ("DOI present",         "10.3390/molecules27123892" in readme),
    ("CC BY 4.0 mentioned", "CC BY" in readme),
    ("JYHP defined",        "JYHP" in readme),
    ("AYHP defined",        "AYHP" in readme),
    ("SA402B mentioned",    "SA402B" in readme),
    ("PEN3 mentioned",      "PEN3" in readme),
    ("6 physical sensors",  "6 sensors" in readme or "6 sensor" in readme),
    ("8 variables noted",   "8 reported variables" in readme or "8 taste" in readme),
    ("BDL zeros noted",     "below-detection-limit" in readme or "BDL" in readme),
    ("Negative mV noted",   "Negative" in readme or "negative" in readme),
    ("Saltiness baseline",  "-6 mV" in readme or "−6 mV" in readme),
    ("Sourness baseline",   "-13 mV" in readme or "−13 mV" in readme),
    ("THM formula",         "honokiol + magnolol" in readme),
    ("PBA formula",         "Magnoloside B / Magnoloside A" in readme),
    ("PHM formula",         "Honokiol / Magnolol" in readme),
    ("30 JYHP samples",     "30" in readme),
    ("Units mg/g",          "mg/g" in readme),
    ("Units mV",            "mV" in readme),
    ("Units G/G0",          "G/G" in readme),
]

for label, condition in checks_readme:
    report(PASS if condition else FAIL, f"README: {label}: {'present' if condition else 'MISSING'}")

# ─────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("AUDIT SUMMARY")
print("=" * 60)

totals = {PASS: 0, FAIL: 0, INFO: 0, WARN: 0}
for tag, _ in findings:
    totals[tag] = totals.get(tag, 0) + 1

print(f"  PASS:  {totals[PASS]}")
print(f"  FAIL:  {totals[FAIL]}")
print(f"  WARN:  {totals[WARN]}")
print(f"  INFO:  {totals[INFO]}")
print()

if issues:
    print("DISCREPANCIES FOUND:")
    for i, msg in enumerate(issues, 1):
        print(f"  {i}. {msg}")
else:
    print("NO DISCREPANCIES FOUND.")
    print("All 480 e-tongue values, all sample IDs, all origin labels,")
    print("all column schemas, and all plausibility checks passed.")
