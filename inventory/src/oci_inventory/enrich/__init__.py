from __future__ import annotations

from typing import Callable, Dict, Optional

from ..auth.providers import AuthContext
from .base import Enricher

EnricherFactory = Callable[[], Enricher]


class EnricherRegistry:
    """
    Registry mapping Resource Search resourceType strings to Enricher factories.
    Falls back to DefaultEnricher when no specific enricher is registered.
    """

    def __init__(self) -> None:
        self._map: Dict[str, EnricherFactory] = {}

    def register(self, resource_type: str, factory: EnricherFactory) -> None:
        self._map[resource_type] = factory

    def is_registered(self, resource_type: str) -> bool:
        return resource_type in self._map

    def registered_resource_types(self) -> list[str]:
        return sorted(self._map.keys())

    def get(self, resource_type: str) -> Enricher:
        factory = self._map.get(resource_type)
        if factory is not None:
            return factory()
        # Fallback to default (import here to avoid circular import at module load)
        from .default import DefaultEnricher
        return DefaultEnricher()


_global_registry = EnricherRegistry()
_enrich_context: Optional[AuthContext] = None


def register_enricher(resource_type: str, factory: EnricherFactory) -> None:
    _global_registry.register(resource_type, factory)


def get_enricher_for(resource_type: str) -> Enricher:
    return _global_registry.get(resource_type)


def is_enricher_registered(resource_type: str) -> bool:
    return _global_registry.is_registered(resource_type)


def list_registered_enricher_resource_types() -> list[str]:
    return _global_registry.registered_resource_types()


def set_enrich_context(ctx: AuthContext) -> None:
    global _enrich_context
    _enrich_context = ctx


def get_enrich_context() -> AuthContext:
    if _enrich_context is None:
        raise RuntimeError("Enrichment context is not set")
    return _enrich_context


try:
    from .oci_metadata import register_metadata_enrichers
    register_metadata_enrichers()
except Exception:
    # Enrichment registration is best-effort; default enricher remains available.
    pass
