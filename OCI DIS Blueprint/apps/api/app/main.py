"""OCI DIS Blueprint — FastAPI application entry point.

API surface implements all route groups from PRD-043:
  /projects, /imports, /catalog, /dictionaries, /patterns,
  /assumptions, /recalculate, /volumetry, /dashboard,
  /justifications, /audit, /exports, /admin/synthetic,
  /ai-reviews, /service-products

OpenAPI 3.1 spec auto-generated at /docs and /openapi.json.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.readiness import check_migration_readiness
from app.routers import (
    agents_router,
    support_router,
    projects_router,
    imports_router,
    catalog_router,
    patterns_router,
    dictionaries_router,
    assumptions_router,
    recalculate_router,
    volumetry_router,
    dashboard_router,
    justifications_router,
    audit_router,
    exports_router,
    service_products_router,
    admin_synthetic_router,
    ai_reviews_router,
    bom_router,
    pricing_router,
)
from app.schemas.readiness import ObjectStorageReadinessResponse, ReadinessResponse
from app.services import storage_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize DB connection pool, verify migrations applied
    yield
    # Shutdown: clean up connections


app = FastAPI(
    title="OCI DIS Blueprint API",
    description=(
        "API-first platform for OCI Integration Design assessment. "
        "Enables engineers to import, govern, calculate volumetry, and export "
        "OCI integration catalogs aligned with Oracle Integration Cloud (OIC) patterns."
    ),
    version="1.0.0",
    openapi_version="3.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount all route groups
API_PREFIX = "/api/v1"
app.include_router(projects_router, prefix=API_PREFIX)
app.include_router(agents_router, prefix=API_PREFIX)
app.include_router(support_router, prefix=API_PREFIX)
app.include_router(imports_router, prefix=API_PREFIX)
app.include_router(catalog_router, prefix=API_PREFIX)
app.include_router(patterns_router, prefix=API_PREFIX)
app.include_router(dictionaries_router, prefix=API_PREFIX)
app.include_router(assumptions_router, prefix=API_PREFIX)
app.include_router(recalculate_router, prefix=API_PREFIX)
app.include_router(volumetry_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(justifications_router, prefix=API_PREFIX)
app.include_router(audit_router, prefix=API_PREFIX)
app.include_router(exports_router, prefix=API_PREFIX)
app.include_router(service_products_router, prefix=API_PREFIX)
app.include_router(admin_synthetic_router, prefix=API_PREFIX)
app.include_router(ai_reviews_router, prefix=API_PREFIX)
app.include_router(pricing_router, prefix=API_PREFIX)
app.include_router(bom_router, prefix=API_PREFIX)


@app.get("/health", tags=["Health"])
@app.get(f"{API_PREFIX}/health", tags=["Health"], include_in_schema=False)
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/readiness", response_model=ReadinessResponse, tags=["Health"])
@app.get(f"{API_PREFIX}/readiness", response_model=ReadinessResponse, tags=["Health"], include_in_schema=False)
async def readiness(db: AsyncSession = Depends(get_db)) -> ReadinessResponse | JSONResponse:
    migration_state = await check_migration_readiness(db)
    storage_ready = True
    storage_hint = None
    try:
        await asyncio.to_thread(storage_service.ensure_bucket)
    except Exception:
        storage_ready = False
        storage_hint = "Verify the S3-compatible endpoint, bucket, network, and Customer Secret Key."
    endpoint = settings.STORAGE_ENDPOINT.lower()
    storage_provider = "MinIO" if "minio" in endpoint or "localhost" in endpoint else "OCI Object Storage"
    payload = ReadinessResponse(
        status="ready" if migration_state.ready and storage_ready else "not_ready",
        version=settings.APP_VERSION,
        database_migrations=migration_state,
        object_storage=ObjectStorageReadinessResponse(
            ready=storage_ready,
            bucket=settings.STORAGE_BUCKET,
            provider=storage_provider,
            recovery_hint=storage_hint,
        ),
    )
    if migration_state.ready and storage_ready:
        return payload
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
