"""
DravyaSense FastAPI application entrypoint.

Startup sequence:
1. Load configuration from .env (or environment variables).
2. Initialise the database (create tables if they don't exist).
3. Configure CORS to allow the React frontend.
4. Register API routers.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import health

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ── FastAPI app ───────────────────────────────────────────────────
app = FastAPI(
    title="DravyaSense API",
    description=(
        "Backend API for PCA and t-SNE visualization of "
        "electronic-tongue sensor data for herbal category separation."
    ),
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup / shutdown lifecycle ──────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    logger.info("DravyaSense API starting up (env=%s)", settings.app_env)
    await init_db()
    logger.info("Database initialised at: %s", settings.database_url)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("DravyaSense API shutting down")


# ── Routers ───────────────────────────────────────────────────────
app.include_router(health.router)

# Future routers (added as each module is implemented):
# app.include_router(datasets.router)
# app.include_router(preprocessing.router)
# app.include_router(pca.router)
# app.include_router(tsne.router)
# app.include_router(evaluation.router)
# app.include_router(reports.router)
