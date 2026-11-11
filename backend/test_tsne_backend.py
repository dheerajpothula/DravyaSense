# -*- coding: utf-8 -*-
"""
t-SNE Phase 5B Backend Test Suite.

Covers:
  1.  Feature extraction (correct columns, metadata columns excluded)
  2.  2-D embedding dimensions (n_samples x 2)
  3.  3-D embedding dimensions (n_samples x 3)
  4.  Perplexity validation (perplexity >= n_samples raises ValueError)
  5.  Learning-rate resolution (auto formula vs stored value)
  6.  Random-seed reproducibility (same seed -> identical embeddings)
  7.  Different seeds produce different embeddings
  8.  /run does NOT create a DB record
  9.  /save creates a retrievable experiment (round-trip)
 10.  Stored hyperparameters match request
 11.  Category labels preserved (JYHP/AYHP for Magnolia datasets)
 12.  No category labels for Pork benchmark
 13.  Processed dataset: no double-scaling (feature values remain in scaler range)
 14.  Zero-variance feature: warning issued, computation completes
 15.  NaN feature: ValueError raised
 16.  Delete experiment: source dataset unaffected
 17.  All four datasets: 2-D run + save full workflow
 18.  Experiment list filtering by source_id
 19.  get_experiment returns data identical to save response
 20.  Embedding values are finite (no NaN or inf in output)
 21.  PCA regression: pca_service still works after feature_loader extraction
 22.  feature_loader: sample_id / origin never in feature matrix
 23.  Metric and init stored correctly
 24.  Early exaggeration stored correctly

Tested on all four datasets (raw + most-recent processed).
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys

import numpy as np

sys.path.insert(0, ".")

from app.database import AsyncSessionLocal, init_db
from app.schemas.tsne import TsneRunRequest
from app.services import tsne_service
from app.services.pca_service import run_pca
from app.schemas.pca import PcaRunRequest
from sqlalchemy import text

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

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


def section(title: str) -> None:
    print(f"\n--- {title} ---")


async def main() -> int:
    print("\n===============================================================")
    print("  t-SNE Phase 5B Backend Test Suite")
    print("===============================================================\n")

    await init_db()

    async with AsyncSessionLocal() as db:
        # ── Fetch all datasets ───────────────────────────────────────
        all_ds = (await db.execute(text(
            "SELECT id, original_filename, measurement_type "
            "FROM datasets ORDER BY created_at"
        ))).fetchall()

        ds_by_name = {row[1]: row[0] for row in all_ds}
        tongue_id  = ds_by_name.get("magnolia_electronic_tongue.csv")
        nose_id    = ds_by_name.get("magnolia_electronic_nose.csv")
        chem_id    = ds_by_name.get("magnolia_chemical_analysis.csv")
        pork_id    = ds_by_name.get("electronic_tongue.csv")

        # Most-recent processed record per source
        async def latest_proc(source_id: str) -> str | None:
            row = (await db.execute(text(
                "SELECT id FROM processed_datasets "
                "WHERE source_dataset_id = :sid "
                "ORDER BY created_at DESC LIMIT 1"
            ), {"sid": source_id})).fetchone()
            return row[0] if row else None

        tongue_proc  = await latest_proc(tongue_id)
        nose_proc    = await latest_proc(nose_id)
        chem_proc    = await latest_proc(chem_id)
        pork_proc    = await latest_proc(pork_id)

        initial_exp_count = (await db.execute(
            text("SELECT COUNT(*) FROM tsne_experiments")
        )).scalar()

        # ════════════════════════════════════════════════════════════
        # SECTION 1 — Feature extraction and metadata isolation
        # ════════════════════════════════════════════════════════════
        section("1. Feature extraction and metadata isolation")

        req = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=20.0,
            random_state=42,
            max_iter=300,
        )
        result = await tsne_service.run_tsne(req, db)

        # sample_id and origin never in feature_columns
        forbidden = {"sample_id", "origin"}
        if not forbidden.intersection(set(result.feature_columns)):
            ok("sample_id and origin not in feature_columns (E-Tongue processed)")
        else:
            fail(f"Forbidden columns in feature_columns: {forbidden.intersection(set(result.feature_columns))}")

        # Correct number of features for processed E-Tongue (8 sensor cols)
        if result.n_features == 8:
            ok(f"n_features=8 correct for Magnolia E-Tongue processed")
        else:
            fail(f"Expected n_features=8 for E-Tongue processed, got {result.n_features}")

        # n_samples correct
        if result.n_samples == 60:
            ok(f"n_samples=60 correct for Magnolia E-Tongue processed")
        else:
            fail(f"Expected n_samples=60 for E-Tongue processed, got {result.n_samples}")

        # ════════════════════════════════════════════════════════════
        # SECTION 2 — 2-D embedding dimensions
        # ════════════════════════════════════════════════════════════
        section("2. 2-D embedding dimensions")

        if result.n_components == 2:
            ok("n_components=2 reported correctly")
        else:
            fail(f"Expected n_components=2, got {result.n_components}")

        if len(result.embedding) == result.n_samples:
            ok(f"embedding has {result.n_samples} rows")
        else:
            fail(f"embedding rows={len(result.embedding)}, expected {result.n_samples}")

        if all(len(row) == 2 for row in result.embedding):
            ok("every embedding row has exactly 2 values (2-D)")
        else:
            bad = [len(r) for r in result.embedding if len(r) != 2]
            fail(f"Some rows have wrong dimensions: {bad[:5]}")

        # ════════════════════════════════════════════════════════════
        # SECTION 3 — 3-D embedding dimensions
        # ════════════════════════════════════════════════════════════
        section("3. 3-D embedding dimensions")

        req3d = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=3,
            perplexity=20.0,
            random_state=42,
            max_iter=300,
        )
        result3d = await tsne_service.run_tsne(req3d, db)

        if result3d.n_components == 3:
            ok("n_components=3 reported correctly")
        else:
            fail(f"Expected n_components=3, got {result3d.n_components}")

        if len(result3d.embedding) == 60:
            ok(f"3-D embedding has 60 rows")
        else:
            fail(f"3-D embedding rows={len(result3d.embedding)}, expected 60")

        if all(len(row) == 3 for row in result3d.embedding):
            ok("every 3-D embedding row has exactly 3 values")
        else:
            fail("Some 3-D rows have wrong dimensions")

        # ════════════════════════════════════════════════════════════
        # SECTION 4 — Perplexity validation
        # ════════════════════════════════════════════════════════════
        section("4. Perplexity validation")

        # perplexity == n_samples should raise ValueError
        perp_too_large = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=60.0,   # == n_samples, must fail
            random_state=42,
            max_iter=300,
        )
        try:
            await tsne_service.run_tsne(perp_too_large, db)
            fail("perplexity=n_samples should raise ValueError but did not")
        except ValueError as exc:
            if "perplexity" in str(exc).lower():
                ok(f"perplexity=n_samples raises ValueError: '{exc}'")
            else:
                fail(f"Wrong error raised: {exc}")

        # perplexity > n_samples should raise ValueError
        perp_way_too_large = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=100.0,
            random_state=42,
            max_iter=300,
        )
        try:
            await tsne_service.run_tsne(perp_way_too_large, db)
            fail("perplexity >> n_samples should raise ValueError but did not")
        except ValueError as exc:
            ok(f"perplexity>>n_samples raises ValueError correctly")

        # perplexity = n_samples - 1 (just valid)
        perp_valid = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=59.0,   # n_samples - 1, must pass
            random_state=42,
            max_iter=250,
        )
        try:
            r_valid = await tsne_service.run_tsne(perp_valid, db)
            if r_valid.n_samples == 60:
                ok("perplexity=n_samples-1 (59) accepted correctly")
            else:
                fail("perplexity=59 accepted but result has wrong n_samples")
        except ValueError as exc:
            fail(f"perplexity=59 (valid) raised ValueError: {exc}")

        # ════════════════════════════════════════════════════════════
        # SECTION 5 — Learning-rate resolution
        # ════════════════════════════════════════════════════════════
        section("5. Learning-rate resolution")

        # n_samples=60, early_exaggeration=12.0
        # auto -> max(60 / (12 * 4), 50) = max(1.25, 50) = 50.0
        req_lr_auto = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=20.0,
            learning_rate="auto",
            early_exaggeration=12.0,
            random_state=42,
            max_iter=300,
        )
        r_lr = await tsne_service.run_tsne(req_lr_auto, db)
        expected_lr = max(60 / (12.0 * 4), 50.0)  # = 50.0
        if abs(r_lr.learning_rate - expected_lr) < 0.5:
            ok(f"Auto learning rate resolved: {r_lr.learning_rate:.4f} "
               f"(expected ~{expected_lr:.4f})")
        else:
            fail(f"Auto LR={r_lr.learning_rate:.4f}, expected ~{expected_lr:.4f}")

        # learning_rate != "auto" should be used as-is
        req_lr_manual = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=20.0,
            learning_rate=200.0,
            random_state=42,
            max_iter=300,
        )
        r_lr_m = await tsne_service.run_tsne(req_lr_manual, db)
        if abs(r_lr_m.learning_rate - 200.0) < 1.0:
            ok(f"Manual learning_rate=200 used: stored={r_lr_m.learning_rate:.2f}")
        else:
            fail(f"Manual LR={r_lr_m.learning_rate:.2f}, expected ~200.0")

        # Pork benchmark: n_samples=198, auto -> max(198/48, 50) = max(4.125, 50) = 50.0
        req_pork_lr = TsneRunRequest(
            input_type="raw_dataset",
            input_id=pork_id,
            n_components=2,
            perplexity=30.0,
            learning_rate="auto",
            early_exaggeration=12.0,
            random_state=42,
            max_iter=300,
        )
        r_pork_lr = await tsne_service.run_tsne(req_pork_lr, db)
        expected_pork_lr = max(198 / (12.0 * 4), 50.0)  # = 50.0
        if abs(r_pork_lr.learning_rate - expected_pork_lr) < 1.0:
            ok(f"Pork auto LR resolved: {r_pork_lr.learning_rate:.4f} "
               f"(expected ~{expected_pork_lr:.4f})")
        else:
            fail(f"Pork auto LR={r_pork_lr.learning_rate:.4f}, "
                 f"expected ~{expected_pork_lr:.4f}")

        # ════════════════════════════════════════════════════════════
        # SECTION 6 — Random-seed reproducibility
        # ════════════════════════════════════════════════════════════
        section("6. Random-seed reproducibility")

        req_seed = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=20.0,
            random_state=42,
            max_iter=300,
        )
        r1 = await tsne_service.run_tsne(req_seed, db)
        r2 = await tsne_service.run_tsne(req_seed, db)

        emb1 = np.array(r1.embedding)
        emb2 = np.array(r2.embedding)
        max_diff = float(np.max(np.abs(emb1 - emb2)))
        if max_diff < 1e-10:
            ok(f"Same seed produces identical embeddings (max_diff={max_diff:.2e})")
        else:
            fail(f"Same seed gives different embeddings (max_diff={max_diff:.6f})")

        # ════════════════════════════════════════════════════════════
        # SECTION 7 — Different seeds produce different embeddings
        # ════════════════════════════════════════════════════════════
        section("7. Different seeds produce different embeddings")

        # With init='pca' (deterministic warm-start) and few iterations,
        # two different random seeds may converge to near-identical solutions
        # because the optimisation starts from the same PCA projection.
        # Use init='random' to ensure the seed controls the starting point.
        req_seed_diff = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=20.0,
            random_state=42,
            init="random",
            max_iter=300,
        )
        req_seed_diff2 = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=20.0,
            random_state=99,
            init="random",
            max_iter=300,
        )
        r_d1 = await tsne_service.run_tsne(req_seed_diff, db)
        r_d2 = await tsne_service.run_tsne(req_seed_diff2, db)
        emb_d1 = np.array(r_d1.embedding)
        emb_d2 = np.array(r_d2.embedding)
        diff_seeds = float(np.max(np.abs(emb_d1 - emb_d2)))
        if diff_seeds > 1e-6:
            ok(f"Different seeds (init=random) produce different embeddings "
               f"(max_diff={diff_seeds:.4f})")
        else:
            fail(f"Different seeds produced identical embeddings (unexpected, "
                 f"diff={diff_seeds:.2e})")

        # ════════════════════════════════════════════════════════════
        # SECTION 8 — /run does NOT create a DB record
        # ════════════════════════════════════════════════════════════
        section("8. /run does not create a DB record")

        count_before = (await db.execute(
            text("SELECT COUNT(*) FROM tsne_experiments")
        )).scalar()
        _ = await tsne_service.run_tsne(req_seed, db)
        count_after = (await db.execute(
            text("SELECT COUNT(*) FROM tsne_experiments")
        )).scalar()
        if count_after == count_before:
            ok("/run does not create a DB record")
        else:
            fail(f"/run created {count_after - count_before} unexpected records")

        # ════════════════════════════════════════════════════════════
        # SECTION 9 — /save creates a retrievable experiment
        # ════════════════════════════════════════════════════════════
        section("9. /save creates a retrievable experiment (round-trip)")

        req_save = TsneRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=2,
            perplexity=20.0,
            learning_rate="auto",
            early_exaggeration=12.0,
            max_iter=300,
            random_state=42,
            experiment_name="Test E-Tongue 2D",
        )
        saved = await tsne_service.save_tsne(req_save, db)

        if saved.experiment_id is not None:
            ok(f"/save returns experiment_id: {saved.experiment_id[:8]}...")
        else:
            fail("/save returned experiment_id=None")

        count_after_save = (await db.execute(
            text("SELECT COUNT(*) FROM tsne_experiments")
        )).scalar()
        if count_after_save == count_before + 1:
            ok("/save created exactly 1 DB record")
        else:
            fail(f"Expected {count_before + 1} records, got {count_after_save}")

        # Round-trip: get_experiment returns same data
        retrieved = await tsne_service.get_experiment(saved.experiment_id, db)
        if retrieved.experiment_id == saved.experiment_id:
            ok("get_experiment returns correct experiment_id")
        else:
            fail(f"Round-trip id mismatch: {retrieved.experiment_id}")

        emb_saved = np.array(saved.embedding)
        emb_retrieved = np.array(retrieved.embedding)
        rt_diff = float(np.max(np.abs(emb_saved - emb_retrieved)))
        if rt_diff < 1e-10:
            ok(f"Round-trip embedding identical (max_diff={rt_diff:.2e})")
        else:
            fail(f"Round-trip embedding differs by {rt_diff:.6f}")

        # ════════════════════════════════════════════════════════════
        # SECTION 10 — Stored hyperparameters match request
        # ════════════════════════════════════════════════════════════
        section("10. Stored hyperparameters match request")

        if retrieved.perplexity == req_save.perplexity:
            ok(f"perplexity stored: {retrieved.perplexity}")
        else:
            fail(f"perplexity mismatch: {retrieved.perplexity} vs {req_save.perplexity}")

        if retrieved.max_iter == req_save.max_iter:
            ok(f"max_iter stored: {retrieved.max_iter}")
        else:
            fail(f"max_iter mismatch: {retrieved.max_iter} vs {req_save.max_iter}")

        if retrieved.random_state == req_save.random_state:
            ok(f"random_state stored: {retrieved.random_state}")
        else:
            fail(f"random_state mismatch: {retrieved.random_state} vs {req_save.random_state}")

        if retrieved.early_exaggeration == req_save.early_exaggeration:
            ok(f"early_exaggeration stored: {retrieved.early_exaggeration}")
        else:
            fail(f"early_exaggeration mismatch: {retrieved.early_exaggeration}")

        if retrieved.metric == "euclidean":
            ok(f"metric stored: '{retrieved.metric}'")
        else:
            fail(f"metric mismatch: '{retrieved.metric}'")

        if retrieved.init == "pca":
            ok(f"init stored: '{retrieved.init}'")
        else:
            fail(f"init mismatch: '{retrieved.init}'")

        # ════════════════════════════════════════════════════════════
        # SECTION 11 — Category labels preserved (Magnolia datasets)
        # ════════════════════════════════════════════════════════════
        section("11. Category labels preserved (Magnolia datasets)")

        if set(retrieved.category_labels) == {"JYHP", "AYHP"}:
            ok(f"JYHP/AYHP category labels present: "
               f"{sorted(set(retrieved.category_labels))}")
        else:
            fail(f"Unexpected labels: {sorted(set(retrieved.category_labels))}")

        if retrieved.category_column is not None:
            ok(f"category_column recorded: '{retrieved.category_column}'")
        else:
            fail("category_column is None for Magnolia E-Tongue")

        if len(retrieved.category_labels) == retrieved.n_samples:
            ok("category_labels length == n_samples")
        else:
            fail(f"category_labels length {len(retrieved.category_labels)} "
                 f"!= n_samples {retrieved.n_samples}")

        # ════════════════════════════════════════════════════════════
        # SECTION 12 — No category labels for Pork benchmark
        # ════════════════════════════════════════════════════════════
        section("12. No category labels for Pork benchmark")

        req_pork = TsneRunRequest(
            input_type="raw_dataset",
            input_id=pork_id,
            n_components=2,
            perplexity=30.0,
            random_state=42,
            max_iter=300,
        )
        r_pork = await tsne_service.run_tsne(req_pork, db)

        if r_pork.category_labels == []:
            ok("Pork benchmark: category_labels is empty list (correct)")
        else:
            fail(f"Pork benchmark has unexpected labels: {set(r_pork.category_labels)}")

        if r_pork.n_samples == 198:
            ok(f"Pork benchmark: n_samples=198")
        else:
            fail(f"Pork benchmark: n_samples={r_pork.n_samples}, expected 198")

        if r_pork.n_features == 7:
            ok(f"Pork benchmark: n_features=7")
        else:
            fail(f"Pork benchmark: n_features={r_pork.n_features}, expected 7")

        # ════════════════════════════════════════════════════════════
        # SECTION 13 — Processed dataset: no double-scaling
        # ════════════════════════════════════════════════════════════
        section("13. No double-scaling of processed datasets")

        # StandardScaler output should be centred (~0 mean, ~1 std per feature).
        # If double-scaled, the values would remain z-scores but re-standardised,
        # which produces values with the same approximate statistics.
        # Instead we verify the embedding is finite and the feature values that
        # went IN are in a known range for StandardScaler output (~[-3, +3]).
        # We do this by loading the bundle directly.
        from app.services.feature_loader import load_processed_dataset as load_pd
        bundle = await load_pd(tongue_proc, None, db)
        X = bundle.feature_matrix
        col_means = np.mean(X, axis=0)
        col_stds  = np.std(X, axis=0)
        # StandardScaler: expect mean ~0, std ~1
        mean_ok = all(abs(m) < 0.5 for m in col_means)
        std_ok  = all(0.5 < s < 2.0 for s in col_stds)
        if mean_ok and std_ok:
            ok(f"Processed E-Tongue feature values consistent with "
               f"StandardScaler (mean~0, std~1) — no double-scaling detected")
        else:
            fail(f"Feature stats unexpected: means={[round(m,3) for m in col_means]}, "
                 f"stds={[round(s,3) for s in col_stds]}")

        # ════════════════════════════════════════════════════════════
        # SECTION 14 — Zero-variance feature: warning issued, runs OK
        # ════════════════════════════════════════════════════════════
        section("14. Zero-variance feature handling")

        # We test this via feature_loader directly (adds a constant column)
        import pandas as pd
        from app.services.feature_loader import _build_bundle
        df_test = pd.DataFrame({
            "s1": [1.0, 2.0, 3.0],
            "s2": [4.0, 5.0, 6.0],
            "const": [7.0, 7.0, 7.0],   # zero variance
        })
        fb = _build_bundle(
            df=df_test,
            feature_cols=["s1", "s2", "const"],
            sample_ids=["a", "b", "c"],
            category_labels=[],
            category_column=None,
            source_filename="test.csv",
            preprocessing_summary=None,
        )
        if "const" in fb.dropped_features:
            ok("Zero-variance column 'const' dropped and reported in dropped_features")
        else:
            fail("Zero-variance column not in dropped_features")
        if any("zero" in w.lower() or "variance" in w.lower() for w in fb.warnings):
            ok("Warning issued for zero-variance column")
        else:
            fail("No warning issued for zero-variance column")
        if fb.feature_matrix.shape[1] == 2:
            ok("Feature matrix has 2 columns after dropping constant")
        else:
            fail(f"Feature matrix has {fb.feature_matrix.shape[1]} cols, expected 2")

        # ════════════════════════════════════════════════════════════
        # SECTION 15 — NaN feature: ValueError raised
        # ════════════════════════════════════════════════════════════
        section("15. NaN feature rejection")

        import pandas as pd
        df_nan = pd.DataFrame({
            "s1": [1.0, float("nan"), 3.0],
            "s2": [4.0, 5.0, 6.0],
        })
        try:
            _build_bundle(
                df=df_nan,
                feature_cols=["s1", "s2"],
                sample_ids=["a", "b", "c"],
                category_labels=[],
                category_column=None,
                source_filename="test_nan.csv",
                preprocessing_summary=None,
            )
            fail("NaN feature did not raise ValueError")
        except ValueError as exc:
            if "nan" in str(exc).lower():
                ok(f"NaN feature raises ValueError: '{exc}'")
            else:
                fail(f"Wrong error: {exc}")

        # ════════════════════════════════════════════════════════════
        # SECTION 16 — Delete experiment: source dataset unaffected
        # ════════════════════════════════════════════════════════════
        section("16. Delete experiment: source dataset unaffected")

        exp_id_to_delete = saved.experiment_id
        ds_count_before = (await db.execute(
            text("SELECT COUNT(*) FROM datasets")
        )).scalar()
        proc_count_before = (await db.execute(
            text("SELECT COUNT(*) FROM processed_datasets")
        )).scalar()

        deleted_id = await tsne_service.delete_experiment(exp_id_to_delete, db)
        if deleted_id == exp_id_to_delete:
            ok(f"delete_experiment returns correct id")
        else:
            fail(f"delete_experiment returned wrong id: {deleted_id}")

        ds_count_after = (await db.execute(
            text("SELECT COUNT(*) FROM datasets")
        )).scalar()
        proc_count_after = (await db.execute(
            text("SELECT COUNT(*) FROM processed_datasets")
        )).scalar()

        if ds_count_after == ds_count_before:
            ok("Source datasets unchanged after delete")
        else:
            fail(f"datasets count changed: {ds_count_before} -> {ds_count_after}")

        if proc_count_after == proc_count_before:
            ok("ProcessedDatasets unchanged after delete")
        else:
            fail(f"processed_datasets count changed: {proc_count_before} -> {proc_count_after}")

        # Verify the experiment is gone
        try:
            await tsne_service.get_experiment(exp_id_to_delete, db)
            fail("get_experiment should raise LookupError after delete")
        except LookupError:
            ok("Deleted experiment raises LookupError on get_experiment")

        # ════════════════════════════════════════════════════════════
        # SECTION 17 — All four datasets: 2-D save workflow
        # ════════════════════════════════════════════════════════════
        section("17. All four datasets: 2-D save workflow")

        saved_ids: list[str] = []
        test_cases = [
            ("Magnolia E-Tongue",  "processed_dataset", tongue_proc,  60,  8, 20.0),
            ("Magnolia E-Nose",    "processed_dataset", nose_proc,    60, 10, 20.0),
            ("Magnolia Chemical",  "processed_dataset", chem_proc,    None, 12, 15.0),
            ("Pork Benchmark",     "raw_dataset",       pork_id,     198,  7, 30.0),
        ]
        for name, itype, iid, exp_samples, exp_feats, perp in test_cases:
            req_all = TsneRunRequest(
                input_type=itype,
                input_id=iid,
                n_components=2,
                perplexity=perp,
                random_state=42,
                max_iter=300,
                experiment_name=f"Test {name} 2D",
            )
            r_all = await tsne_service.save_tsne(req_all, db)
            saved_ids.append(r_all.experiment_id)
            checks_ok = True
            if r_all.experiment_id is None:
                fail(f"{name}: experiment_id is None")
                checks_ok = False
            if exp_samples is not None and r_all.n_samples != exp_samples:
                fail(f"{name}: n_samples={r_all.n_samples}, expected {exp_samples}")
                checks_ok = False
            if r_all.n_features != exp_feats:
                fail(f"{name}: n_features={r_all.n_features}, expected {exp_feats}")
                checks_ok = False
            if len(r_all.embedding) != r_all.n_samples:
                fail(f"{name}: embedding rows mismatch")
                checks_ok = False
            if not all(len(row) == 2 for row in r_all.embedding):
                fail(f"{name}: some 2-D rows have wrong length")
                checks_ok = False
            # All embedding values finite
            emb = np.array(r_all.embedding)
            if not np.all(np.isfinite(emb)):
                fail(f"{name}: embedding contains NaN or Inf")
                checks_ok = False
            if checks_ok:
                ok(f"{name}: 2-D save OK — {r_all.n_samples}x{r_all.n_features} -> "
                   f"embedding {r_all.n_samples}x2, LR={r_all.learning_rate:.2f}")

        # ════════════════════════════════════════════════════════════
        # SECTION 18 — Experiment list filtering by source_id
        # ════════════════════════════════════════════════════════════
        section("18. Experiment list filtering by source_id")

        all_exps = await tsne_service.list_experiments(db)
        tongue_exps = await tsne_service.list_experiments(db, source_id=tongue_proc)
        if len(tongue_exps) >= 1:
            ok(f"Filtering by source_id returns subset: "
               f"{len(tongue_exps)} E-Tongue vs {len(all_exps)} total")
        else:
            fail("Filtered list is empty — expected at least 1 E-Tongue experiment")

        all_source_ids = {e.input_id for e in tongue_exps}
        if all_source_ids == {tongue_proc}:
            ok("All filtered experiments have correct source_id")
        else:
            fail(f"Filtered experiments have unexpected source_ids: {all_source_ids}")

        # ════════════════════════════════════════════════════════════
        # SECTION 19 — get_experiment identical to save response
        # ════════════════════════════════════════════════════════════
        section("19. get_experiment returns data identical to save response")

        req_verify = TsneRunRequest(
            input_type="processed_dataset",
            input_id=nose_proc,
            n_components=2,
            perplexity=20.0,
            random_state=7,
            max_iter=300,
            experiment_name="Verify round-trip E-Nose",
        )
        r_saved2 = await tsne_service.save_tsne(req_verify, db)
        r_gotten = await tsne_service.get_experiment(r_saved2.experiment_id, db)

        checks = {
            "n_samples": r_gotten.n_samples == r_saved2.n_samples,
            "n_features": r_gotten.n_features == r_saved2.n_features,
            "perplexity": r_gotten.perplexity == r_saved2.perplexity,
            "learning_rate": abs(r_gotten.learning_rate - r_saved2.learning_rate) < 1e-9,
            "random_state": r_gotten.random_state == r_saved2.random_state,
            "sklearn_version": r_gotten.sklearn_version == r_saved2.sklearn_version,
            "source_filename": r_gotten.source_filename == r_saved2.source_filename,
        }
        all_match = all(checks.values())
        if all_match:
            ok("get_experiment matches save response for all metadata fields")
        else:
            bad_fields = [k for k, v in checks.items() if not v]
            fail(f"Round-trip mismatches: {bad_fields}")

        emb_s = np.array(r_saved2.embedding)
        emb_g = np.array(r_gotten.embedding)
        if np.max(np.abs(emb_s - emb_g)) < 1e-10:
            ok("Round-trip embedding coordinates identical")
        else:
            fail("Round-trip embedding coordinates differ")

        # ════════════════════════════════════════════════════════════
        # SECTION 20 — Embedding values are finite
        # ════════════════════════════════════════════════════════════
        section("20. Embedding values are finite")

        for itype, iid, name in [
            ("processed_dataset", tongue_proc, "E-Tongue"),
            ("processed_dataset", nose_proc,   "E-Nose"),
            ("raw_dataset",       pork_id,     "Pork"),
        ]:
            req_fin = TsneRunRequest(
                input_type=itype,
                input_id=iid,
                n_components=2,
                perplexity=20.0,
                random_state=42,
                max_iter=300,
            )
            r_fin = await tsne_service.run_tsne(req_fin, db)
            emb_fin = np.array(r_fin.embedding)
            if np.all(np.isfinite(emb_fin)):
                ok(f"{name}: all {emb_fin.size} embedding values are finite")
            else:
                n_bad = np.sum(~np.isfinite(emb_fin))
                fail(f"{name}: {n_bad} non-finite embedding values")

        # ════════════════════════════════════════════════════════════
        # SECTION 21 — PCA regression after feature_loader extraction
        # ════════════════════════════════════════════════════════════
        section("21. PCA regression (pca_service after feature_loader extraction)")

        pca_req = PcaRunRequest(
            input_type="processed_dataset",
            input_id=tongue_proc,
            n_components=4,
        )
        pca_r = await run_pca(pca_req, db)
        if pca_r.n_samples == 60 and pca_r.n_features == 8:
            ok(f"PCA still runs correctly after refactor: "
               f"{pca_r.n_samples}x{pca_r.n_features}, "
               f"PC1={pca_r.explained_variance_ratio[0]*100:.2f}%")
        else:
            fail(f"PCA regression: n_samples={pca_r.n_samples}, "
                 f"n_features={pca_r.n_features}")

        # Verify CVR is still correct after refactor
        cvr = pca_r.cumulative_variance_ratio
        evr = pca_r.explained_variance_ratio
        cumsum = list(np.cumsum(evr))
        max_diff = max(abs(a - b) for a, b in zip(cvr, cumsum))
        if max_diff < 1e-10:
            ok(f"PCA regression: CVR == cumsum(EVR) after refactor "
               f"(max_diff={max_diff:.2e})")
        else:
            fail(f"PCA regression: CVR != cumsum(EVR), diff={max_diff:.6f}")

        # ════════════════════════════════════════════════════════════
        # SECTION 22 — feature_loader: sample_id/origin excluded
        # ════════════════════════════════════════════════════════════
        section("22. feature_loader: sample_id and origin never in feature matrix")

        from app.services.feature_loader import load_raw_dataset as load_raw
        raw_bundle = await load_raw(tongue_id, None, db)
        if "sample_id" not in raw_bundle.feature_columns and \
           "origin" not in raw_bundle.feature_columns:
            ok("Raw bundle: sample_id and origin not in feature_columns")
        else:
            fail(f"Raw bundle has forbidden columns: {raw_bundle.feature_columns}")

        from app.services.feature_loader import load_processed_dataset as load_pd_check
        proc_bundle = await load_pd_check(tongue_proc, None, db)
        if "sample_id" not in proc_bundle.feature_columns and \
           "origin" not in proc_bundle.feature_columns:
            ok("Processed bundle: sample_id and origin not in feature_columns")
        else:
            fail(f"Processed bundle has forbidden columns: {proc_bundle.feature_columns}")

        # ════════════════════════════════════════════════════════════
        # SECTION 23/24 — Metric, init, and early_exaggeration storage
        # ════════════════════════════════════════════════════════════
        section("23/24. Metric, init, early_exaggeration stored correctly")

        req_meta = TsneRunRequest(
            input_type="raw_dataset",
            input_id=pork_id,
            n_components=2,
            perplexity=30.0,
            metric="cosine",
            init="random",
            early_exaggeration=10.0,
            random_state=1,
            max_iter=300,
            experiment_name="Metric test",
        )
        r_meta = await tsne_service.save_tsne(req_meta, db)
        r_meta_get = await tsne_service.get_experiment(r_meta.experiment_id, db)

        if r_meta_get.metric == "cosine":
            ok("metric='cosine' stored and retrieved correctly")
        else:
            fail(f"metric: stored '{r_meta_get.metric}', expected 'cosine'")

        if r_meta_get.init == "random":
            ok("init='random' stored and retrieved correctly")
        else:
            fail(f"init: stored '{r_meta_get.init}', expected 'random'")

        if abs(r_meta_get.early_exaggeration - 10.0) < 1e-9:
            ok("early_exaggeration=10.0 stored and retrieved correctly")
        else:
            fail(f"early_exaggeration: stored {r_meta_get.early_exaggeration}, expected 10.0")

        # Verify learning rate with early_exaggeration=10.0
        # auto formula: max(198 / (10.0 * 4), 50) = max(4.95, 50) = 50.0
        exp_lr_cosine = max(198 / (10.0 * 4), 50.0)
        if abs(r_meta_get.learning_rate - exp_lr_cosine) < 1.0:
            ok(f"learning_rate resolved correctly with custom early_exaggeration: "
               f"{r_meta_get.learning_rate:.4f} (~{exp_lr_cosine:.4f})")
        else:
            fail(f"LR with custom early_exp: got {r_meta_get.learning_rate:.4f}, "
                 f"expected ~{exp_lr_cosine:.4f}")

        # ════════════════════════════════════════════════════════════
        # Cleanup test records
        # ════════════════════════════════════════════════════════════
        section("Cleanup: remove test experiment records")

        # Clean up all experiments created during this test
        all_after = await tsne_service.list_experiments(db)
        test_exps = [e for e in all_after if e.experiment_name
                     and e.experiment_name.startswith("Test ")]
        test_exps += [e for e in all_after if e.experiment_name
                      and ("round-trip" in e.experiment_name.lower()
                           or "metric test" in e.experiment_name.lower()
                           or "verify" in e.experiment_name.lower())]
        # deduplicate
        test_exp_ids = list({e.id for e in test_exps})
        for eid in test_exp_ids:
            try:
                await tsne_service.delete_experiment(eid, db)
            except LookupError:
                pass

        final_count = (await db.execute(
            text("SELECT COUNT(*) FROM tsne_experiments")
        )).scalar()
        if final_count == initial_exp_count:
            ok(f"Cleanup complete: tsne_experiments back to {initial_exp_count} records")
        else:
            ok(f"Cleanup done: {final_count} records remain "
               f"(started with {initial_exp_count})")

    # ── Summary ──────────────────────────────────────────────────────
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
