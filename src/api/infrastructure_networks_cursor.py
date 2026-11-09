"""Purpose-bound HMAC cursors for infrastructure-networks reads."""

from __future__ import annotations

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "INFRASTRUCTURE_NETWORKS_CURSOR_TTL_SECONDS",
    "InfrastructureNetworksCursorCodec",
    "InfrastructureNetworksCursorError",
]

INFRASTRUCTURE_NETWORKS_CURSOR_TTL_SECONDS = 900
INFRASTRUCTURE_NETWORKS_ROUTES_CURSOR_PURPOSE = "infrastructure_networks_routes"
InfrastructureNetworksCursorCodec = DiplomacyCursorCodec
InfrastructureNetworksCursorError = DiplomacyCursorError
