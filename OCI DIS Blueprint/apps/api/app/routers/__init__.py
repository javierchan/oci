# Router registry — all route groups imported here and mounted in main.py
from .projects import router as projects_router
from .imports import router as imports_router
from .catalog import router as catalog_router
from .patterns import router as patterns_router
from .dictionaries import router as dictionaries_router
from .assumptions import router as assumptions_router
from .recalculate import router as recalculate_router
from .volumetry import router as volumetry_router
from .dashboard import router as dashboard_router
from .justifications import router as justifications_router
from .audit import router as audit_router
from .exports import router as exports_router
from .services import router as services_router

__all__ = [
    "projects_router",
    "imports_router",
    "catalog_router",
    "patterns_router",
    "dictionaries_router",
    "assumptions_router",
    "recalculate_router",
    "volumetry_router",
    "dashboard_router",
    "justifications_router",
    "audit_router",
    "exports_router",
    "services_router",
]
