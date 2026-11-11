"""
SQLAlchemy async database engine and session factory.

Development:  SQLite via aiosqlite (zero configuration)
Production:   swap DATABASE_URL in .env to a PostgreSQL asyncpg URL
"""
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Ensure the data directory exists before SQLite tries to create the file
Path("./data").mkdir(parents=True, exist_ok=True)

# SQLite-specific: disable "check_same_thread" via connect_args
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_async_engine(
    settings.database_url,
    echo=(settings.app_env == "development"),
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        yield session


# Columns added after the initial schema release — must be patched into
# pre-existing SQLite databases non-destructively.
_SQLITE_MIGRATIONS: list[tuple[str, str]] = [
    # (column_name, ADD COLUMN SQL fragment)
    ("measurement_type",  "ALTER TABLE datasets ADD COLUMN measurement_type  TEXT"),
    ("source_attribution","ALTER TABLE datasets ADD COLUMN source_attribution TEXT"),
    ("column_units",      "ALTER TABLE datasets ADD COLUMN column_units       TEXT"),
]


async def _apply_sqlite_migrations() -> None:
    """
    Add any missing columns to an existing datasets table.
    Each ALTER TABLE is attempted; if the column already exists SQLite
    raises an OperationalError which we silently ignore.
    This is safe to run on every startup (idempotent).
    """
    if not settings.database_url.startswith("sqlite"):
        return  # PostgreSQL etc. handle migrations externally

    async with engine.begin() as conn:
        # Fetch the current column names from the table's PRAGMA info
        result = await conn.execute(text("PRAGMA table_info(datasets)"))
        existing = {row[1] for row in result.fetchall()}  # row[1] = column name

        for col_name, ddl in _SQLITE_MIGRATIONS:
            if col_name not in existing:
                logger.info("DB migration: adding column '%s' to datasets table", col_name)
                await conn.execute(text(ddl))


async def init_db() -> None:
    """Create all tables on startup (idempotent), then apply column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _apply_sqlite_migrations()
