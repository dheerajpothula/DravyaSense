"""
TsneExperiment ORM model.

Stores the full configuration and embedding coordinates of a single
t-SNE run.  All effective hyperparameters — including the resolved
learning rate and early exaggeration — are persisted so every experiment
is fully reproducible.

Design rules
────────────
• No sklearn estimator objects are ever pickled.  Embedding coordinates
  are stored as a JSON array of arrays.
• learning_rate is stored as the resolved float, not the string "auto".
  The resolved value is read from the fitted estimator's learning_rate_
  attribute when available (sklearn 1.5.2+).
• random_state is required (NOT NULL) for every saved experiment.
  Unsaved /run results carry the seed in the response body only.
• The source dataset and processed dataset files are never modified.
• t-SNE preserves local neighbourhood structure.  Distances between
  clusters are NOT directly interpretable.  This caveat is recorded in
  the API documentation and shown in the frontend.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TsneExperiment(Base):
    __tablename__ = "tsne_experiments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Optional user-supplied label ──────────────────────────
    experiment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Input reference ───────────────────────────────────────
    # input_type: "raw_dataset" | "processed_dataset"
    input_type:            Mapped[str] = mapped_column(String(32),  nullable=False)
    input_id:              Mapped[str] = mapped_column(String(36),  nullable=False)
    source_filename:       Mapped[str] = mapped_column(String(255), nullable=False)
    # Human-readable summary of upstream preprocessing (scaling, imputation …)
    preprocessing_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Feature matrix description ────────────────────────────
    n_samples:       Mapped[int] = mapped_column(Integer, nullable=False)
    n_features:      Mapped[int] = mapped_column(Integer, nullable=False)
    # JSON list of column names that entered the feature matrix
    feature_columns: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Metadata arrays (never in feature matrix) ─────────────
    sample_ids:      Mapped[str]       = mapped_column(Text, nullable=False)   # JSON list
    category_labels: Mapped[str]       = mapped_column(Text, nullable=False)   # JSON list (may be [])
    category_column: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── t-SNE hyperparameters (all stored for reproducibility) ─
    n_components:      Mapped[int]   = mapped_column(Integer, nullable=False)
    perplexity:        Mapped[float] = mapped_column(Float,   nullable=False)
    # Resolved float — never the string "auto"
    learning_rate:     Mapped[float] = mapped_column(Float,   nullable=False)
    early_exaggeration: Mapped[float] = mapped_column(Float,  nullable=False)
    max_iter:          Mapped[int]   = mapped_column(Integer, nullable=False)
    # Required — no null seeds in saved experiments
    random_state:      Mapped[int]   = mapped_column(Integer, nullable=False)
    metric:            Mapped[str]   = mapped_column(String(64), nullable=False,
                                                      default="euclidean")
    init:              Mapped[str]   = mapped_column(String(32), nullable=False,
                                                      default="pca")

    # ── Embedding result ──────────────────────────────────────
    # JSON [[x, y], …] for 2-D or [[x, y, z], …] for 3-D
    # Shape: n_samples × n_components
    embedding: Mapped[str] = mapped_column(Text, nullable=False)

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
            f"<TsneExperiment id={self.id!r} "
            f"input={self.input_type}:{self.input_id[:8]}\u2026 "
            f"perp={self.perplexity} n_comp={self.n_components}>"
        )
