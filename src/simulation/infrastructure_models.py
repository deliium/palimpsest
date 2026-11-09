"""Bounded canonical ``infrastructure-networks-snapshot-v1`` document.

Independent of ``analysis``: experiments maps harvest outputs into these DTOs.
No civilization infrastructure score field exists anywhere on the snapshot.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "INFRASTRUCTURE_FORBIDDEN_FIELD_NAMES",
    "INFRASTRUCTURE_MAX_ASSETS",
    "INFRASTRUCTURE_MAX_BYTES",
    "INFRASTRUCTURE_NETWORKS_PUBLICATION_PREFIX",
    "INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY",
    "INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION",
    "INFRASTRUCTURE_NETWORKS_STORE_VERSION",
    "InfrastructureAssetRecord",
    "InfrastructureNetworksArtifactError",
    "InfrastructureNetworksSnapshot",
    "InfrastructureNetworksSummaryRecord",
    "empty_infrastructure_networks_snapshot",
    "require_infrastructure_asset_id",
]

INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION: Final[str] = (
    "infrastructure-networks-snapshot-v1"
)
INFRASTRUCTURE_NETWORKS_STORE_VERSION: Final[str] = "infrastructure-networks-store-v1"
INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY: Final[str] = "infrastructure-networks.v1"
INFRASTRUCTURE_NETWORKS_PUBLICATION_PREFIX: Final[str] = "infra-pub-"

INFRASTRUCTURE_MAX_BYTES: Final[int] = 4 * 1024 * 1024
INFRASTRUCTURE_MAX_ASSETS: Final[int] = 64

INFRASTRUCTURE_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "score",
        "infrastructure_score",
        "civilization_score",
        "planner",
        "auto_maintain",
        "owner_id",
        "crew",
        "nation_id",
        "grid",
        "coordinate",
        "composite",
        "rank",
        "raw_owner_id",
        "raw_agent_id",
        "frame_body",
        "evidence_body",
    }
)

_ASSET_PATTERN: Final[re.Pattern[str]] = re.compile(r"^infra-[0-9a-f]{32}$")
_PUBLICATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{INFRASTRUCTURE_NETWORKS_PUBLICATION_PREFIX}[0-9a-f]{{32}}$"
)
_HEX64: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_KINDS: Final[frozenset[str]] = frozenset(
    {
        "road",
        "bridge",
        "storage",
        "well",
        "irrigation",
        "communication_marker",
        "trade_post",
        "large_shelter",
    }
)
_TOPOLOGIES: Final[frozenset[str]] = frozenset({"node", "edge"})
_STATUSES: Final[frozenset[str]] = frozenset({"operational", "damaged", "destroyed"})
_COVERAGES: Final[frozenset[str]] = frozenset(
    {"complete", "partial", "not_applicable", "observed", "missing"}
)

_LOG: Final[logging.Logger] = logging.getLogger("simulation.infrastructure.models")


class InfrastructureNetworksArtifactError(ValueError):
    """Fail-closed snapshot error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.debug(
            "infrastructure_networks_artifact_invalid reason_code=%s", reason_code
        )
        super().__init__(reason_code)


def require_infrastructure_asset_id(value: object) -> str:
    if not isinstance(value, str) or not _ASSET_PATTERN.match(value):
        raise InfrastructureNetworksArtifactError("infrastructure_networks_invalid_id")
    return value


def require_publication_id(value: object) -> str:
    if not isinstance(value, str) or not _PUBLICATION_PATTERN.match(value):
        raise InfrastructureNetworksArtifactError(
            "infrastructure_networks_invalid_publication_id"
        )
    return value


def _stable(name: str, value: object) -> str:
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise InfrastructureNetworksArtifactError(
            "infrastructure_networks_invalid_value"
        ) from exc


def _tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except ValueError as exc:
        raise InfrastructureNetworksArtifactError(
            "infrastructure_networks_invalid_value"
        ) from exc


def _reject_forbidden(mapping: object) -> None:
    if not isinstance(mapping, dict):
        return
    for key, value in mapping.items():
        if isinstance(key, str) and (
            key in INFRASTRUCTURE_FORBIDDEN_FIELD_NAMES or key.endswith("_score")
        ):
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_forbidden_result_field"
            )
        if isinstance(value, dict):
            _reject_forbidden(value)


@dataclass(frozen=True, slots=True)
class InfrastructureAssetRecord:
    asset_id: str
    kind: str
    topology: str
    status: str
    integrity: float
    location_id: str
    endpoint_location_id: str | None
    effects_active: bool
    created_tick: int
    last_maintained_tick: int
    ticks_since_maintained: int
    linked_project_id: str
    linked_structure_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "asset_id", require_infrastructure_asset_id(self.asset_id)
        )
        kind = _stable("kind", self.kind)
        topology = _stable("topology", self.topology)
        status = _stable("status", self.status)
        if kind not in _KINDS:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_kind"
            )
        if topology not in _TOPOLOGIES:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_topology"
            )
        if status not in _STATUSES:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_status"
            )
        if (
            isinstance(self.integrity, bool)
            or type(self.integrity) is not float
            or self.integrity != self.integrity
            or self.integrity < 0.0
            or self.integrity > 1.0
        ):
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_integrity"
            )
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "topology", topology)
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "location_id", _stable("location_id", self.location_id)
        )
        if self.endpoint_location_id is not None:
            object.__setattr__(
                self,
                "endpoint_location_id",
                _stable("endpoint_location_id", self.endpoint_location_id),
            )
        if type(self.effects_active) is not bool:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_value"
            )
        object.__setattr__(
            self, "created_tick", _tick("created_tick", self.created_tick)
        )
        object.__setattr__(
            self,
            "last_maintained_tick",
            _tick("last_maintained_tick", self.last_maintained_tick),
        )
        object.__setattr__(
            self,
            "ticks_since_maintained",
            _tick("ticks_since_maintained", self.ticks_since_maintained),
        )
        object.__setattr__(
            self,
            "linked_project_id",
            _stable("linked_project_id", self.linked_project_id),
        )
        if self.linked_structure_id is not None:
            object.__setattr__(
                self,
                "linked_structure_id",
                _stable("linked_structure_id", self.linked_structure_id),
            )
        if topology == "edge" and self.endpoint_location_id is None:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_topology"
            )
        if topology == "node" and self.endpoint_location_id is not None:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_topology"
            )


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksSummaryRecord:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    policy_version: str
    asset_count: int
    node_count: int
    edge_count: int
    operational_count: int
    damaged_count: int
    destroyed_count: int
    effects_active_count: int
    coverage: str = "not_applicable"

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _stable("run_id", self.run_id))
        if self.publication_id:
            object.__setattr__(
                self, "publication_id", require_publication_id(self.publication_id)
            )
        if self.digest and _HEX64.match(self.digest) is None:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_digest"
            )
        if self.schema_version != INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_unsupported_schema"
            )
        if self.policy_version != INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_unsupported_policy"
            )
        for name in (
            "asset_count",
            "node_count",
            "edge_count",
            "operational_count",
            "damaged_count",
            "destroyed_count",
            "effects_active_count",
        ):
            object.__setattr__(self, name, _tick(name, getattr(self, name)))
        coverage = _stable("coverage", self.coverage)
        if coverage not in _COVERAGES:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_coverage"
            )
        object.__setattr__(self, "coverage", coverage)


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksSnapshot:
    summary: InfrastructureNetworksSummaryRecord
    assets: tuple[InfrastructureAssetRecord, ...]
    digest: str = ""
    publication_id: str = ""
    schema_version: str = INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION
    policy_version: str = INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY

    def __post_init__(self) -> None:
        if len(self.assets) > INFRASTRUCTURE_MAX_ASSETS:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_size_limit"
            )
        asset_ids = [asset.asset_id for asset in self.assets]
        if len(set(asset_ids)) != len(asset_ids):
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_duplicate_asset"
            )
        object.__setattr__(
            self,
            "assets",
            tuple(sorted(self.assets, key=lambda asset: asset.asset_id)),
        )
        if self.schema_version != INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_unsupported_schema"
            )
        if self.policy_version != INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_unsupported_policy"
            )
        if self.publication_id:
            object.__setattr__(
                self, "publication_id", require_publication_id(self.publication_id)
            )
        if self.digest and _HEX64.match(self.digest) is None:
            raise InfrastructureNetworksArtifactError(
                "infrastructure_networks_invalid_digest"
            )


def empty_infrastructure_networks_snapshot(
    *, run_id: str
) -> InfrastructureNetworksSnapshot:
    summary = InfrastructureNetworksSummaryRecord(
        run_id=run_id,
        publication_id="",
        digest="",
        schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
        policy_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
        asset_count=0,
        node_count=0,
        edge_count=0,
        operational_count=0,
        damaged_count=0,
        destroyed_count=0,
        effects_active_count=0,
        coverage="not_applicable",
    )
    return InfrastructureNetworksSnapshot(summary=summary, assets=())
