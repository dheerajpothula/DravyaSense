"""
Health-check router.

GET /api/health — returns application status, service name and version.
Used by the frontend to verify backend connectivity.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse, summary="Backend health check")
async def health_check() -> HealthResponse:
    """
    Returns a simple health payload.
    A 200 response confirms the backend is reachable and configured.
    """
    return HealthResponse(
        status="ok",
        service="DravyaSense API",
        version=settings.app_version,
        environment=settings.app_env,
    )
