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
from redis.asyncio import Redis
from starlette.middleware.gzip import GZipMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.auth import authorize_project_request
from app.core.readiness import check_migration_readiness
from app.core.observability import RequestTelemetryMiddleware
from app.routers import (
    auth_router,
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
    external_capture_router,
    project_coordination_router,
    users_router,
)
from app.schemas.readiness import (
    AppKnowledgeReadinessResponse,
    ObjectStorageReadinessResponse,
    ReadinessResponse,
    RedisReadinessResponse,
)
from app.knowledge.builder import load_knowledge_base, provider_embedding_errors
from app.services import storage_service

settings = get_settings()


def create_readiness_redis_client() -> Redis:
    """Build the readiness-only Redis client without altering shared client factories."""

    return Redis.from_url(settings.REDIS_URL)


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
app.add_middleware(RequestTelemetryMiddleware)

# Mount all route groups
API_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_PREFIX)
protected_dependencies = [Depends(authorize_project_request)]
app.include_router(projects_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(agents_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(support_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(imports_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(catalog_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(patterns_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(dictionaries_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(assumptions_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(recalculate_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(volumetry_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(dashboard_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(justifications_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(audit_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(exports_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(service_products_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(admin_synthetic_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(ai_reviews_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(pricing_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(bom_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(external_capture_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(project_coordination_router, prefix=API_PREFIX, dependencies=protected_dependencies)
app.include_router(users_router, prefix=API_PREFIX, dependencies=protected_dependencies)


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
        await asyncio.to_thread(storage_service.check_bucket_access)
    except Exception:
        storage_ready = False
        storage_hint = "Verify the S3-compatible endpoint, bucket, network, and Customer Secret Key."
    endpoint = settings.STORAGE_ENDPOINT.lower()
    storage_provider = "MinIO" if "minio" in endpoint or "localhost" in endpoint else "OCI Object Storage"
    redis_ready = True
    redis_hint = None
    redis_client = create_readiness_redis_client()
    try:
        await asyncio.wait_for(redis_client.ping(), timeout=2.0)
    except Exception:
        redis_ready = False
        redis_hint = "Verify the shared Redis endpoint, credentials, network policy, and TLS settings."
    finally:
        await redis_client.aclose()
    knowledge_ready = True
    knowledge_source_hash = None
    knowledge_runtime_version = None
    knowledge_embedding_model = None
    knowledge_vector_count = 0
    knowledge_hint = None
    try:
        knowledge = await asyncio.to_thread(load_knowledge_base)
        derived = knowledge.get("derived")
        if not isinstance(derived, dict):
            raise ValueError("Derived App knowledge is missing")
        provider_spaces = derived.get("embedding_spaces")
        provider = provider_spaces.get("provider") if isinstance(provider_spaces, dict) else None
        units = derived.get("retrieval_units")
        knowledge_source_hash = str(knowledge.get("source_hash") or "")
        knowledge_runtime_version = str(knowledge.get("runtime_version") or "")
        if isinstance(provider, dict):
            knowledge_embedding_model = str(provider.get("model") or "")
        knowledge_vector_count = len(units) if isinstance(units, list) else 0
        embedding_errors = provider_embedding_errors(
            derived,
            expected_model=settings.OCI_GENAI_EMBEDDING_MODEL_NAME,
        )
        if embedding_errors:
            raise ValueError("; ".join(embedding_errors))
    except Exception:
        knowledge_ready = False
        knowledge_hint = (
            "Regenerate and publish one complete App Knowledge artifact for the configured "
            "embedding model; verify every replica reports the same source hash and runtime version."
        )
    payload = ReadinessResponse(
        status=(
            "ready"
            if migration_state.ready and storage_ready and redis_ready and knowledge_ready
            else "not_ready"
        ),
        version=settings.APP_VERSION,
        database_migrations=migration_state,
        object_storage=ObjectStorageReadinessResponse(
            ready=storage_ready,
            bucket=settings.STORAGE_BUCKET,
            provider=storage_provider,
            recovery_hint=storage_hint,
        ),
        redis=RedisReadinessResponse(ready=redis_ready, recovery_hint=redis_hint),
        app_knowledge=AppKnowledgeReadinessResponse(
            ready=knowledge_ready,
            source_hash=knowledge_source_hash,
            runtime_version=knowledge_runtime_version,
            embedding_model=knowledge_embedding_model,
            vector_count=knowledge_vector_count,
            recovery_hint=knowledge_hint,
        ),
    )
    if migration_state.ready and storage_ready and redis_ready and knowledge_ready:
        return payload
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
