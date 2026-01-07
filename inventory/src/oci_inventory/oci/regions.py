from __future__ import annotations

from typing import List

from ..auth.providers import AuthContext
from .clients import list_region_subscriptions


def get_subscribed_regions(ctx: AuthContext) -> List[str]:
    """
    Return sorted list of subscribed region identifiers (e.g., 'us-ashburn-1').
    """
    regions = list_region_subscriptions(ctx)
    # Already sorted in clients, but enforce here for determinism
    return sorted(regions)