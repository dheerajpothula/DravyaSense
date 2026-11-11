"""
ProcessedDataset ORM model.

Stores metadata about a dataset that has been through the Preprocessing
Studio pipeline.  The processed CSV lives on disk at `processed_filename`
inside the processed-datasets directory.

The raw source dataset is never modified — this is a derived artefact.
Pipeline configuration is stored as a readable JSON string (never a pickled
scikit-learn Pipeline object) so it remains human-auditable and
version-safe.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProcessedDataset(Base):
    __tablename__ = "processed_datasets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Source reference ─────────────────────────────────────
    # FK to datasets.id (no hard constraint — keeps migration simple)
    source_dataset_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_filename:    Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Processed file identity ───────────────────────────────
    processed_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_size_bytes:    Mapped[int]  = mapped_column(Integer, nullable=False)

    # ── Shape ─────────────────────────────────────────────────
    row_count:           Mapped[int] = mapped_column(Integer, nullable=False)
    column_count:        Mapped[int] = mapped_column(Integer, nullable=False)
    sensor_column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_value_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Pipeline configuration (readable JSON) ────────────────
    # selected_features:  JSON list of column names that were transformed
    # pipeline_config:    JSON object with imputation/scaling/outlier settings
    # transformations:     JSON list of human-readable step descriptions
    # column_units:        JSON copied from the source dataset for display
    selected_features:     Mapped[str]      = mapped_column(Text, nullable=False, default="[]")
    pipeline_config:       Mapped[str]      = mapped_column(Text, nullable=False, default="{}")
    transformations_applied: Mapped[str]    = mapped_column(Text, nullable=False, default="[]")
    column_units:          Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Reproducibility ───────────────────────────────────────
    sklearn_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Timestamp ─────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ProcessedDataset id={self.id!r} "
            f"source={self.source_filename!r}>"
        )
