# Magnolia Officinalis Cortex – Processed Research Datasets

## Source

**Paper:**  
Jing W., Zhao X., Li M., Hu X., Cheng X., Ma S., Wei F.  
"Application of Multiple-Source Data Fusion for the Discrimination of Two Botanical Origins of  
Magnolia Officinalis Cortex Based on E-Nose Measurements, E-Tongue Measurements, and Chemical Analysis."  
*Molecules* 2022, 27, 3892.  
DOI: https://doi.org/10.3390/molecules27123892  
Published: 17 June 2022. Open access (CC BY 4.0).

**Original files (unchanged):**
- `../molecules-27-03892.pdf` — main research paper (15 pages)
- `../molecules-27-03892-s001.zip` — supplementary material ZIP
  - Contains: `molecules-1726795-supplementary.pdf` (7 pages)

**Data extracted from:** Supplementary PDF, Tables S1, S2, S3.  
All values are taken directly from the published supplementary tables. No values have been
fabricated, imputed, estimated, or modified.

---

## Study Design

**Botanical origins studied:**
| Code | Full name | Collection site | n |
|------|-----------|-----------------|---|
| JYHP | *Magnolia officinalis* Rehd. et Wils. | Enshi City, Hubei Province, China | 30 |
| AYHP | *Magnolia officinalis* Rehd. et Wils. var. biloba Rehd. et Wils. | Yongzhou City, Hunan Province, China | 30 |

**Total samples:** 60 (S1–S60). S1–S30 = JYHP; S31–S60 = AYHP.  
Samples were derived from the diameter-at-breast-height position, shade-dried after collection,
and pulverized to powder (50-mesh, 300 µm) before all measurements.

---

## Files in This Directory

| File | Rows | Feature cols | Source table |
|------|------|-------------|--------------|
| `magnolia_electronic_tongue.csv` | 60 | 8 | Supplementary Table S2 |
| `magnolia_electronic_nose.csv` | 60 | 10 | Supplementary Table S1 |
| `magnolia_chemical_analysis.csv` | 60 | 12 | Supplementary Table S3 |
| `README.md` | — | — | This file |
| `_validate.py` | — | — | Validation script |

---

## Dataset 1 — magnolia_electronic_tongue.csv

**Instrument:** Taste sensing system SA402B (Insent Inc., Atsugi-shi, Japan)  
**Physical sensors:** 6 sensors with differently composed lipid membranes  
**Replication:** 4 measurements per sample; last 3 used; mean of 3 reported  
**Reference solution:** 30 mM KCl in 0.3 mM tartaric acid (simulated artificial saliva)

> **Important:** The 8 reported variables do NOT represent 8 independent physical sensors.
> Five primary taste measurements come from 5 taste sensors; 3 aftertaste (CPA) measurements
> are obtained by re-measuring the same sensors after a brief cleaning step.

**Columns:**

| Column | Description | Physical sensor | Unit | Tasteless-point baseline |
|--------|-------------|-----------------|------|--------------------------|
| `sample_id` | Sample identifier (S1–S60) | — | — | — |
| `origin` | Botanical origin (JYHP / AYHP) | — | — | — |
| `sourness_mV` | Sourness taste response | CA0 | mV | −13 mV (tasteless-point baseline) |
| `bitterness_mV` | Bitterness taste response | C00 | mV | 0 mV |
| `astringency_mV` | Astringency taste response | AE1 | mV | 0 mV |
| `aftertaste_bitterness_mV` | Aftertaste of bitterness (CPA) | C00 | mV | 0 mV |
| `aftertaste_astringency_mV` | Aftertaste of astringency (CPA) | AE1 | mV | 0 mV |
| `umami_mV` | Umami taste response | AAE | mV | 0 mV |
| `richness_mV` | Richness/body response | — | mV | 0 mV |
| `saltiness_mV` | Saltiness taste response | CT0 | mV | −6 mV (tasteless-point baseline) |

**Scientific notes:**
- Negative sourness and saltiness values are correct and expected — they reflect measurements
  below the tasteless-point baseline for those sensors.
- All 60 saltiness values (range −11.51 to −17.48 mV) are below the −6 mV tasteless threshold.
  The paper correctly excludes saltiness from statistical analysis for this reason.
- Some richness values in AYHP (S49–S60) are slightly negative (−0.13 to −0.07 mV); these
  are genuine instrument readings, not errors.
- JYHP samples (S11–S30) show lower richness values (~0.01–0.30) compared to S1–S10
  (~0.60–0.75), reflecting sub-group variation within JYHP.

---

## Dataset 2 — magnolia_electronic_nose.csv

**Instrument:** PEN3 portable electronic nose (Schwerin, Germany)  
**Physical sensors:** 10 metal oxide semiconductor (MOS) sensors  
**Unit:** G/G₀ — dimensionless ratio of sensor conductivity after contact with sample gas (G)
to conductivity after cleaning with activated-charcoal-filtered gas (G₀)  
**Replication:** 3 measurements per sample; data at 90 s adsorption equilibrium; mean of 3 reported  
**Headspace preparation:** 1 g powder in 50 mL chamber; incubated 30°C for 60 min; flow 400 mL/min

**Columns:**

| Column | Sensor name | Sensitive substances | Threshold |
|--------|-------------|----------------------|-----------|
| `sample_id` | Sample identifier (S1–S60) | — | — |
| `origin` | Botanical origin (JYHP / AYHP) | — | — |
| `W1C` | W1C | Aromatic (toluene) | 10 mL·m⁻³ |
| `W5S` | W5S | Hydrocarbon (NO₂) | 1 mL·m⁻³ |
| `W3C` | W3C | Aromatic (benzene) | 10 mL·m⁻³ |
| `W6S` | W6S | Hydrogen (H₂) | 100 mL·m⁻³ |
| `W5C` | W5C | Aromatic and aliphatic (propane) | 1 mL·m⁻³ |
| `W1S` | W1S | Broad range / methane (CH₄) | 100 mL·m⁻³ |
| `W1W` | W1W | Sulfur organic (H₂S) | 1 mL·m⁻³ |
| `W2S` | W2S | Broad range alcohol (NO) | 100 mL·m⁻³ |
| `W2W` | W2W | Sulfur and chlorinate (H₂S) | 1 mL·m⁻³ |
| `W3S` | W3S | Methane and aliphatic (CH₄) | 10 mL·m⁻³ |

**Scientific notes:**
- No negative values. All G/G₀ readings are positive (range ~0.3–1.5 for most sensors;
  W1W and W2W can reach ~38–45 in JYHP).
- W1W, W2W, W5S, W1S are high-variance sensors — they contribute most to JYHP/AYHP separation
  (identified as key discriminators in PLS-VIP analysis in the paper).
- W3S, W6S, W1C, W3C, W5C are lower-variance sensors with G/G₀ near 1.0.
- The paper found no correlation between e-nose sensor responses and β-eudesmol content,
  suggesting the e-nose captures the overall volatile profile rather than a single compound.

---

## Dataset 3 — magnolia_chemical_analysis.csv

**Instruments:**
- UHPLC (8 non-volatile compounds): Waters Acquity UPLC BEH-C18 column; gradient elution;
  compounds identified by UV spectrum or retention time against reference standards.
- GC-FID (β-eudesmol, 1 volatile compound): Agilent HP-5 column (30 m × 0.25 mm × 0.25 µm);
  FID at 250°C; nitrogen carrier; initial 80°C → 250°C at 8°C/min.

**Replication:** 2 measurements per sample; mean of 2 reported.

**Columns:**

| Column | Compound / Feature | Type | Method | Unit |
|--------|-------------------|------|--------|------|
| `sample_id` | Sample identifier (S1–S60) | Identifier | — | — |
| `origin` | Botanical origin (JYHP / AYHP) | Category | — | — |
| `syringin_mg_g` | Syringin | Phenylethanoid glycoside | UHPLC | mg/g |
| `magnoflorine_mg_g` | Magnoflorine | Alkaloid | UHPLC | mg/g |
| `magnoloside_B_mg_g` | Magnoloside B | Phenylethanoid glycoside; quality marker | UHPLC | mg/g |
| `magnoloside_A_mg_g` | Magnoloside A | Phenylethanoid glycoside; quality marker | UHPLC | mg/g |
| `honokiol_mg_g` | Honokiol | Neolignan; major bioactive | UHPLC | mg/g |
| `magnolol_mg_g` | Magnolol | Neolignan; major bioactive | UHPLC | mg/g |
| `piperitylmagnolol_mg_g` | Piperitylmagnolol | Phenolic; key JYHP differentiator | UHPLC | mg/g |
| `magnocurarine_mg_g` | Magnocurarine | Alkaloid | UHPLC | mg/g |
| `beta_eudesmol_mg_g` | β-eudesmol | Volatile sesquiterpenoid | GC-FID | mg/g |
| `THM_mg_g` | Total Honokiol + Magnolol | Derived: honokiol + magnolol | Derived | mg/g |
| `PBA_ratio` | Proportionate feature B/A | Derived: Magnoloside B / Magnoloside A | Derived | dimensionless |
| `PHM_ratio` | Proportionate feature H/M | Derived: Honokiol / Magnolol | Derived | dimensionless |

**Scientific notes:**
- THM (Total Honokiol + Magnolol) is the primary quality control marker in the Chinese
  Pharmacopoeia (ChP); minimum specification is 2.0% (= 20 mg/g). JYHP samples show higher
  THM (mean ~53 mg/g) vs. AYHP (mean ~22 mg/g).
- PHM (Proportionate Feature of Honokiol and Magnolol) = Honokiol / Magnolol. This is the
  ratio of the two major bioactive neolignans. Values > 1 indicate honokiol dominance;
  values < 1 indicate magnolol dominance. The paper describes PHM as the "proportionate
  feature of honokiol and magnolol" (not a fraction of total).
- PBA (Proportionate Feature of Magnolosides B and A) = Magnoloside B / Magnoloside A.
- Zero values for `piperitylmagnolol_mg_g` (S27, S53) and `beta_eudesmol_mg_g` (S2, S5, S7,
  S27, S51) represent below-detection-limit (BDL) concentrations. They are stored as 0.000
  exactly as published in the supplementary table. These are NOT missing values.
- THM, PBA, and PHM are derived from other columns in this dataset. They are collinear with
  their source measurements (THM = honokiol + magnolol exactly; PBA = MagB / MagA; PHM =
  honokiol / magnolol). For PCA, consider running separate analyses with and
  without these derived features.
- S16 (JYHP) has the highest magnoloside_B value (54.275 mg/g) in the entire dataset.
- S17 (JYHP) has anomalously low magnoloside_B (3.521 mg/g), contributing to its
  misclassification in HCA (noted in the paper).
- S18 (JYHP) has the highest THM value (99.564 mg/g) in the dataset.

---

## Column Role Assignments (for DravyaSense import)

| Column | Role |
|--------|------|
| `sample_id` | `sample_id` |
| `origin` | `category` |
| All measurement columns | `sensor` |

The `origin` column has exactly 2 unique values (JYHP, AYHP) across 60 rows (3.3% cardinality).
It will be auto-detected as `category` by the column detector's value-based heuristic.

---

## Validation

Run `_validate.py` to verify all three files:

```
python data/research/magnolia/processed/_validate.py
```

All 25 checks pass (row counts, unique IDs, origin balance, cross-file alignment, 15 spot-checked values).

---

## Attribution

Data extracted from the published supplementary material:  
Jing W. et al., *Molecules* 2022, 27, 3892. https://doi.org/10.3390/molecules27123892  
Licensed under Creative Commons Attribution (CC BY) 4.0.  
https://creativecommons.org/licenses/by/4.0/

Original research files preserved unchanged at `data/research/magnolia/`.
