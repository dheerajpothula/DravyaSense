"""
Application configuration via environment variables.
Uses pydantic-settings for type-safe env loading.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_version: str = "0.1.0"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/dravyasense.db"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # File uploads
    upload_dir: Path = Path("./uploads")
    max_upload_size_mb: int = 50

    @property
    def upload_dir_abs(self) -> Path:
        """Return an absolute path to the upload directory."""
        return self.upload_dir.resolve()


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
