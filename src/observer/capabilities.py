"""Advertised observer capabilities and supported protocols.

Advisory metadata only. No frame, semantic type, layout, or route changes: the
capability names let a client learn what the server supports before opening a
stream, and they are never a capability-flag or configuration payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION, OBSERVER_PROTOCOL_VERSION


class ObserverCapability(StrEnum):
    """Closed observer capability vocabulary."""

    STRUCTURED_MANIFEST = "structured_manifest"
    REPLAY_CURSORS = "replay_cursors"
    AGGREGATE_DEMOGRAPHICS = "aggregate_demographics"
    CIVILIZATION_OVERLAYS = "civilization_overlays"
    MULTI_SCALE_SUMMARIES = "multi_scale_summaries"
    ORGANIZATION_ROWS = "organization_rows"
    NETWORK_ROWS = "network_rows"
    EPIDEMIC_ROWS = "epidemic_rows"
    CONFLICT_ROWS = "conflict_rows"
    DISASTER_ROWS = "disaster_rows"


OBSERVER_CAPABILITIES: Final[tuple[ObserverCapability, ...]] = (
    ObserverCapability.STRUCTURED_MANIFEST,
    ObserverCapability.REPLAY_CURSORS,
    ObserverCapability.AGGREGATE_DEMOGRAPHICS,
    ObserverCapability.CIVILIZATION_OVERLAYS,
)

RESERVED_OBSERVER_CAPABILITIES: Final[tuple[ObserverCapability, ...]] = (
    ObserverCapability.MULTI_SCALE_SUMMARIES,
    ObserverCapability.ORGANIZATION_ROWS,
    ObserverCapability.NETWORK_ROWS,
    ObserverCapability.EPIDEMIC_ROWS,
    ObserverCapability.CONFLICT_ROWS,
    ObserverCapability.DISASTER_ROWS,
)

SUPPORTED_OBSERVER_PROTOCOLS: Final[tuple[str, ...]] = (OBSERVER_PROTOCOL_VERSION,)
RESERVED_OBSERVER_PROTOCOL_VERSION: Final[str] = "observer-protocol-v2"


@dataclass(frozen=True, slots=True)
class ObserverCapabilityManifest:
    """What one server instance advertises before a stream is opened."""

    protocol_version: str = OBSERVER_PROTOCOL_VERSION
    layout_schema_version: str = OBSERVER_LAYOUT_SCHEMA_VERSION
    supported_protocols: tuple[str, ...] = SUPPORTED_OBSERVER_PROTOCOLS
    capabilities: tuple[str, ...] = field(
        default_factory=lambda: tuple(OBSERVER_CAPABILITIES)
    )
    reserved_capabilities: tuple[str, ...] = field(
        default_factory=lambda: tuple(RESERVED_OBSERVER_CAPABILITIES)
    )
    read_only: bool = True

    def __post_init__(self) -> None:
        if not self.supported_protocols:
            raise ValueError("observer_protocols_empty")
        if RESERVED_OBSERVER_PROTOCOL_VERSION in self.supported_protocols:
            raise ValueError("observer_reserved_protocol_served")
        if self.protocol_version not in self.supported_protocols:
            raise ValueError("observer_protocol_not_supported")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("observer_capabilities_duplicate")
        if len(set(self.reserved_capabilities)) != len(self.reserved_capabilities):
            raise ValueError("observer_capabilities_duplicate")
        if set(self.capabilities) & set(self.reserved_capabilities):
            raise ValueError("observer_capabilities_overlap")
        if self.read_only is not True:
            raise ValueError("observer_manifest_not_read_only")


def observer_capability_manifest() -> ObserverCapabilityManifest:
    """The v1 manifest served by ``GET /version``."""
    return ObserverCapabilityManifest()


def observer_capability_payload() -> dict[str, object]:
    """JSON-safe manifest values for additive ``/version`` fields."""
    manifest = observer_capability_manifest()
    return {
        "protocol_version": manifest.protocol_version,
        "layout_schema_version": manifest.layout_schema_version,
        "supported_protocols": list(manifest.supported_protocols),
        "capabilities": list(manifest.capabilities),
        "reserved_capabilities": list(manifest.reserved_capabilities),
        "read_only": manifest.read_only,
    }


__all__ = [
    "OBSERVER_CAPABILITIES",
    "RESERVED_OBSERVER_CAPABILITIES",
    "RESERVED_OBSERVER_PROTOCOL_VERSION",
    "SUPPORTED_OBSERVER_PROTOCOLS",
    "ObserverCapability",
    "ObserverCapabilityManifest",
    "observer_capability_manifest",
    "observer_capability_payload",
]
