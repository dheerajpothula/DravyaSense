"""
Dataset ORM model.

Stores metadata about an uploaded sensor file.
The raw file is never modified — it lives on disk at `file_path`.
Column-role assignments (sensor / sample_id / category / ignored)
are stored as JSON so they can be updated after upload.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── File identity ─────────────────────────────────────────
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename:   Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_size_bytes:   Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type:         Mapped[str] = mapped_column(String(64),  nullable=False)

    # ── Shape ─────────────────────────────────────────────────
    row_count:    Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Column role assignments (JSON string) ─────────────────
    # Schema: {"col_name": "sensor" | "sample_id" | "category" | "ignored"}
    column_roles: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # ── Quality flags ─────────────────────────────────────────
    missing_value_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sensor_column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Optional user note ────────────────────────────────────
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Scientific metadata ───────────────────────────────────
    # One of: electronic_tongue | electronic_nose | chemical_analysis | None
    measurement_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Free-text research citation / DOI
    source_attribution: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Per-column measurement units stored as a JSON string
    # Schema: {"col_name": "mV"} — only sensor columns need entries
    column_units: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Dataset id={self.id!r} file={self.original_filename!r}>"
