# -*- coding: utf-8 -*-
"""
Regression test for the processed dataset dropdown label improvement.

Verifies:
  1. All four E-Tongue processed records have distinct creation timestamps
     at HH:MM resolution — i.e. the new label format produces four unique
     strings.
  2. Loading each record via feature_loader still yields exactly 60 samples
     and 8 measurement variables.
  3. No NaN or infinity in any of the four feature matrices.
  4. sample_id and origin are excluded from all four feature matrices.
  5. The four numeric matrices are all identical (byte-identical CSV confirmed
     in the audit; this confirms the runtime path produces the same values).
  6. Record 3 (c11ed7f7 — different selected_features order) produces the
     same feature matrix as Record 1 when columns are aligned by name.
  7. PCA backend still runs cleanly on each record (regression guard).
  8. t-SNE backend still runs cleanly on each record (regression guard).
"""
from __future__ import annotations

import asyncio
import json
import sys

import numpy as np

sys.path.insert(0, ".")

from app.database import AsyncSessionLocal, init_db
from app.services.feature_loader import load_processed_dataset
from app.services.pca_service import run_pca
from app.services.tsne_service import run_tsne
from app.schemas.pca import PcaRunRequest
from app.schemas.tsne import TsneRunRequest
from sqlalchemy import text

GREEN  = "\033[92m"
RED    = "\033[91m"
RESET  = "\033[0m"
passed = 0
failed = 0
failures: list[str] = []


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"{GREEN} PASS{RESET}  {msg}")


def fail(msg: str) -> None:
    global failed
    failures.append(msg)
    print(f"{RED} FAIL{RESET}  {msg}")


# The four processed E-Tongue record IDs (chronological order)
RECORD_IDS = [
    "3fa53496-ccc4-46bb-aead-40f0b760f873",  # 06:57:29
    "ec642524-0d0f-473d-9544-12df4bb4ae0a",  # 09:29:34
    "c11ed7f7-3e39-4040-a9ca-73c6f57351cf",  # 10:06:10  <- different feat order
    "b9b57b58-08d7-4256-a5eb-8e93d6262825",  # 12:01:17
]


async def main() -> int:
    print("\n===============================================================")
    print("  Dropdown Label Regression + Feature Loader Verification")
    print("===============================================================\n")

    await init_db()

    async with AsyncSessionLocal() as db:

        # ── 1. Distinct HH:MM timestamps ────────────────────────────
        rows = (await db.execute(text(
            "SELECT id, created_at FROM processed_datasets "
            "WHERE id IN ('3fa53496-ccc4-46bb-aead-40f0b760f873',"
            "             'ec642524-0d0f-473d-9544-12df4bb4ae0a',"
            "             'c11ed7f7-3e39-4040-a9ca-73c6f57351cf',"
            "             'b9b57b58-08d7-4256-a5eb-8e93d6262825') "
            "ORDER BY created_at"
        ))).fetchall()

        timestamps = {}
        for r in rows:
            ts = str(r[1])
            timestamps[r[0]] = ts
            print(f"  {r[0][:8]}...  created_at: {ts}")

        # Extract HH:MM strings (the new label segment)
        hhmm_labels = []
        for r in rows:
            ts = str(r[1])   # "2026-11-09 06:57:29" or similar
            # Take HH:MM from the time component
            time_part = ts.split(" ")[1] if " " in ts else ts.split("T")[1]
            hhmm = ":".join(time_part.split(":")[:2])
            hhmm_labels.append(hhmm)
        print(f"\n  HH:MM labels: {hhmm_labels}")

        if len(set(hhmm_labels)) == 4:
            ok(f"All four records have distinct HH:MM timestamps: {hhmm_labels}")
        else:
            fail(f"HH:MM labels are not all distinct: {hhmm_labels}")

        # Construct the full label as the frontend would produce it
        # (simulated — we verify the time segment is unique)
        full_labels = [
            f"Magnolia E-tongue | StandardScaler | 60 samples | Nov 9 | {hm}"
            for hm in hhmm_labels
        ]
        if len(set(full_labels)) == 4:
            ok("All four full dropdown labels are unique")
            for lbl in full_labels:
                print(f"    {lbl}")
        else:
            fail(f"Full labels not all unique: {full_labels}")

        # ── 2-4. Feature loader: shape, NaN, infinity, exclusions ───
        print()
        bundles = []
        for rid in RECORD_IDS:
            bundle = await load_processed_dataset(rid, None, db)
            bundles.append((rid, bundle))

            n_rows, n_cols = bundle.feature_matrix.shape
            nan_count      = int(np.isnan(bundle.feature_matrix).sum())
            inf_count      = int(np.isinf(bundle.feature_matrix).sum())
            sample_id_in   = "sample_id" in bundle.feature_columns
            origin_in      = "origin"    in bundle.feature_columns

            shape_ok = (n_rows == 60 and n_cols == 8)
            nan_ok   = (nan_count == 0)
            inf_ok   = (inf_count == 0)
            excl_ok  = (not sample_id_in and not origin_in)

            if shape_ok:
                ok(f"{rid[:8]}...: shape=(60, 8)")
            else:
                fail(f"{rid[:8]}...: unexpected shape=({n_rows}, {n_cols})")

            if nan_ok and inf_ok:
                ok(f"{rid[:8]}...: no NaN or Inf in feature matrix")
            else:
                fail(f"{rid[:8]}...: NaN={nan_count}, Inf={inf_count}")

            if excl_ok:
                ok(f"{rid[:8]}...: sample_id and origin correctly excluded")
            else:
                fail(f"{rid[:8]}...: forbidden columns present "
                     f"(sample_id={sample_id_in}, origin={origin_in})")

        # ── 5. Numeric identity across all four records ──────────────
        print()
        base_id, base_bundle = bundles[0]
        base_cols   = base_bundle.feature_columns
        base_sorted = sorted(base_cols)

        for rid, bundle in bundles[1:]:
            # Align both to sorted column order before comparing
            idx_base  = [base_cols.index(c)           for c in base_sorted]
            idx_other = [bundle.feature_columns.index(c) for c in base_sorted]
            mat_base  = base_bundle.feature_matrix[:, idx_base]
            mat_other = bundle.feature_matrix[:, idx_other]
            max_diff  = float(np.max(np.abs(mat_base - mat_other)))
            if max_diff < 1e-12:
                ok(f"{rid[:8]}...: feature matrix identical to Record 1 "
                   f"(max_diff={max_diff:.2e})")
            else:
                fail(f"{rid[:8]}...: feature matrix differs from Record 1 "
                     f"(max_diff={max_diff:.6e})")

        # ── 6. Record 3 column-order difference is safe ─────────────
        print()
        _, r3_bundle = bundles[2]
        if r3_bundle.feature_columns != base_bundle.feature_columns:
            ok(f"Record 3 has different feature_columns order (expected): "
               f"{r3_bundle.feature_columns}")
        else:
            ok("Record 3 feature_columns order same as Record 1 (no reorder needed)")

        # Verify they produce same values when aligned
        idx_b = [base_cols.index(c)                  for c in base_sorted]
        idx_3 = [r3_bundle.feature_columns.index(c)  for c in base_sorted]
        diff  = float(np.max(np.abs(
            base_bundle.feature_matrix[:, idx_b] -
            r3_bundle.feature_matrix[:, idx_3]
        )))
        if diff < 1e-12:
            ok(f"Record 3 aligned numeric values == Record 1 (max_diff={diff:.2e})")
        else:
            fail(f"Record 3 aligned values differ from Record 1 (diff={diff:.2e})")

        # ── 7. PCA regression on each record ────────────────────────
        print()
        for rid in RECORD_IDS:
            pca_req = PcaRunRequest(
                input_type="processed_dataset",
                input_id=rid,
                n_components=4,
            )
            pca_r = await run_pca(pca_req, db)
            evr = pca_r.explained_variance_ratio
            cvr = pca_r.cumulative_variance_ratio
            import numpy as np_inner
            cumsum = list(np_inner.cumsum(evr))
            max_diff_pca = max(abs(a - b) for a, b in zip(cvr, cumsum))
            if pca_r.n_samples == 60 and pca_r.n_features == 8 and max_diff_pca < 1e-10:
                ok(f"{rid[:8]}...: PCA OK — 60×8, PC1={evr[0]*100:.2f}%, "
                   f"CVR=cumsum (diff={max_diff_pca:.2e})")
            else:
                fail(f"{rid[:8]}...: PCA issue — "
                     f"shape=({pca_r.n_samples},{pca_r.n_features}), "
                     f"cvr_diff={max_diff_pca:.2e}")

        # ── 8. t-SNE regression on each record ──────────────────────
        print()
        for rid in RECORD_IDS:
            tsne_req = TsneRunRequest(
                input_type="processed_dataset",
                input_id=rid,
                n_components=2,
                perplexity=20.0,
                random_state=42,
                max_iter=300,
            )
            tsne_r = await run_tsne(tsne_req, db)
            emb    = np.array(tsne_r.embedding)
            all_finite = bool(np.all(np.isfinite(emb)))
            if (tsne_r.n_samples == 60 and tsne_r.n_features == 8
                    and emb.shape == (60, 2) and all_finite):
                ok(f"{rid[:8]}...: t-SNE OK — 60×8 -> embedding 60×2, finite")
            else:
                fail(f"{rid[:8]}...: t-SNE issue — "
                     f"shape=({tsne_r.n_samples},{tsne_r.n_features}), "
                     f"emb={emb.shape}, finite={all_finite}")

    print("\n===============================================================")
    print(f"  Results: {passed} passed, {failed} failed")
    if failures:
        print("\n  Failures:")
        for f in failures:
            print(f"    - {f}")
    print("===============================================================\n")
    return failed


exit_code = asyncio.run(main())
sys.exit(exit_code)
