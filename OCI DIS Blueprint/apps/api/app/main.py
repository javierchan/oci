"""OCI DIS Blueprint — FastAPI application entry point.

API surface implements all route groups from PRD-043:
  /projects, /imports, /catalog, /dictionaries, /patterns,
  /assumptions, /services, /recalculate, /volumetry, /dashboard,
  /justifications, /audit, /exports

OpenAPI 3.1 spec auto-generated at /docs and /openapi.json.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import (
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
    services_router,
)

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
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all route groups
API_PREFIX = "/api/v1"
app.include_router(projects_router, prefix=API_PREFIX)
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
app.include_router(services_router, prefix=API_PREFIX)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
