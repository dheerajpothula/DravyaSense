"""
PcaExperiment ORM model.

Stores the full configuration and numerical results of a single PCA run.
Computation uses sklearn.decomposition.PCA — results are stored as
readable JSON arrays so they are human-auditable and version-safe.

No sklearn Pipeline object is ever pickled.
The source dataset and processed dataset files are never modified.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PcaExperiment(Base):
    __tablename__ = "pca_experiments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Optional user-supplied label ──────────────────────────
    experiment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Input reference ───────────────────────────────────────
    # input_type: "raw_dataset" | "processed_dataset"
    input_type:             Mapped[str] = mapped_column(String(32),  nullable=False)
    input_id:               Mapped[str] = mapped_column(String(36),  nullable=False)
    source_filename:        Mapped[str] = mapped_column(String(255), nullable=False)
    # Human-readable summary of upstream preprocessing (scaling, imputation …)
    preprocessing_summary:  Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Feature matrix description ────────────────────────────
    n_samples:       Mapped[int] = mapped_column(Integer, nullable=False)
    n_features:      Mapped[int] = mapped_column(Integer, nullable=False)
    n_components:    Mapped[int] = mapped_column(Integer, nullable=False)
    feature_columns: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list

    # ── Metadata arrays (never entered the feature matrix) ────
    sample_ids:      Mapped[str]      = mapped_column(Text, nullable=False)  # JSON list
    category_labels: Mapped[str]      = mapped_column(Text, nullable=False)  # JSON list (may be [])
    category_column: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── Numerical results (all JSON arrays) ──────────────────
    explained_variance_ratio:  Mapped[str] = mapped_column(Text, nullable=False)  # [float, …]
    cumulative_variance_ratio: Mapped[str] = mapped_column(Text, nullable=False)  # [float, …]
    # scores:   n_samples × n_components  (each row is one sample's PC coordinates)
    scores:   Mapped[str] = mapped_column(Text, nullable=False)
    # loadings: n_components × n_features (each row is one PC's loading vector)
    loadings: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Reproducibility ───────────────────────────────────────
    sklearn_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Warnings from computation ─────────────────────────────
    warnings: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list

    # ── Timestamp ─────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<PcaExperiment id={self.id!r} "
            f"input={self.input_type}:{self.input_id[:8]}…>"
        )
