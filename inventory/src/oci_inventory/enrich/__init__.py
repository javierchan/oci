from __future__ import annotations

from typing import Callable, Dict

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

    def get(self, resource_type: str) -> Enricher:
        factory = self._map.get(resource_type)
        if factory is not None:
            return factory()
        # Fallback to default (import here to avoid circular import at module load)
        from .default import DefaultEnricher
        return DefaultEnricher()


_global_registry = EnricherRegistry()


def register_enricher(resource_type: str, factory: EnricherFactory) -> None:
    _global_registry.register(resource_type, factory)


def get_enricher_for(resource_type: str) -> Enricher:
    return _global_registry.get(resource_type)