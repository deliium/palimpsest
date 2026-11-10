"""Bounded canonical ``supply-chains-snapshot-v1`` document."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MAX_SUPPLY_SNAPSHOT_BOTTLENECKS",
    "MAX_SUPPLY_SNAPSHOT_CHAINS",
    "MAX_SUPPLY_SNAPSHOT_EDGES",
    "MAX_SUPPLY_SNAPSHOT_LINEAGE",
    "MAX_SUPPLY_SNAPSHOT_LOCATIONS",
    "MAX_SUPPLY_SNAPSHOT_ORGANIZATIONS",
    "MAX_SUPPLY_SNAPSHOT_STAGES",
    "MAX_SUPPLY_SNAPSHOT_WINDOWS",
    "SUPPLY_CHAIN_SNAPSHOT_POLICY",
    "SUPPLY_CHAIN_SNAPSHOT_VERSION",
    "SUPPLY_SNAPSHOT_COVERAGES",
    "SUPPLY_SNAPSHOT_FORBIDDEN_KEYS",
    "SUPPLY_SNAPSHOT_STATUSES",
    "SupplyBottleneckRecord",
    "SupplyChainLineageRecord",
    "SupplyChainRecord",
    "SupplyChainSnapshot",
    "SupplyChainSnapshotError",
    "SupplyChainSummaryRecord",
    "SupplyDependencyRecord",
    "SupplyLocationRecord",
    "SupplyOrganizationRecord",
    "SupplyStageRecord",
    "empty_supply_chain_snapshot",
]

SUPPLY_CHAIN_SNAPSHOT_VERSION: Final[str] = "supply-chains-snapshot-v1"
SUPPLY_CHAIN_SNAPSHOT_POLICY: Final[str] = "supply-chains.v1"
MAX_SUPPLY_SNAPSHOT_STAGES: Final[int] = 4_096
MAX_SUPPLY_SNAPSHOT_EDGES: Final[int] = 16_384
MAX_SUPPLY_SNAPSHOT_CHAINS: Final[int] = 4_096
MAX_SUPPLY_SNAPSHOT_BOTTLENECKS: Final[int] = 4_096
MAX_SUPPLY_SNAPSHOT_LOCATIONS: Final[int] = 4_096
MAX_SUPPLY_SNAPSHOT_ORGANIZATIONS: Final[int] = 2_048
MAX_SUPPLY_SNAPSHOT_WINDOWS: Final[int] = 512
MAX_SUPPLY_SNAPSHOT_LINEAGE: Final[int] = 16_384

SUPPLY_SNAPSHOT_COVERAGES: Final[tuple[str, ...]] = (
    "complete",
    "partial",
    "missing",
)
SUPPLY_SNAPSHOT_STATUSES: Final[tuple[str, ...]] = (
    "emerged",
    "continued",
    "transformed",
    "split",
    "merge",
    "dissolved",
)
SUPPLY_SNAPSHOT_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "price",
        "cost",
        "currency",
        "money",
        "quota",
        "allocation",
        "optimizer",
        "plan_score",
        "priority_score",
        "recommendation",
        "rank",
        "severity",
    }
)

_COVERAGES: Final[frozenset[str]] = frozenset(SUPPLY_SNAPSHOT_COVERAGES)
_STATUSES: Final[frozenset[str]] = frozenset(SUPPLY_SNAPSHOT_STATUSES)
_LOG: Final[logging.Logger] = logging.getLogger("simulation.supply_chain.models")


class SupplyChainSnapshotError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _stable(name: str, value: object) -> str:
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_value") from exc


def _count(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except ValueError as exc:
        raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_value") from exc


def _window(value: object) -> int:
    index = _count("window_index", value)
    if index >= MAX_SUPPLY_SNAPSHOT_WINDOWS:
        raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_window")
    return index


def _coverage(value: object) -> str:
    if not isinstance(value, str) or value not in _COVERAGES:
        raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_coverage")
    return value


def _names(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_value")
    return value


def _forbidden(instance: object) -> None:
    names = {field.name for field in fields(instance)}  # type: ignore[arg-type]
    if names & SUPPLY_SNAPSHOT_FORBIDDEN_KEYS:
        raise SupplyChainSnapshotError("supply_chain_snapshot_forbidden_key")


@dataclass(frozen=True, slots=True)
class SupplyStageRecord:
    stage_token: str
    window_index: int
    recipe_id: str
    action: str
    location_token: str
    actor_token: str
    item_names: tuple[str, ...]
    completed: bool
    attempt: bool
    duration_ticks: int
    created_item_token: str
    cause: str
    coverage: str

    def __post_init__(self) -> None:
        _forbidden(self)
        for name in (
            "stage_token",
            "recipe_id",
            "action",
            "location_token",
            "actor_token",
            "created_item_token",
            "cause",
        ):
            _stable(name, getattr(self, name))
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "item_names", _names(self.item_names))
        object.__setattr__(
            self, "duration_ticks", _count("duration_ticks", self.duration_ticks)
        )
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class SupplyDependencyRecord:
    edge_token: str
    window_index: int
    from_kind: str
    from_token: str
    to_kind: str
    to_token: str
    edge_kind: str
    recipe_id: str
    observed_count: int
    completed_count: int
    share_milli: int
    created_elsewhere_count: int
    coverage: str

    def __post_init__(self) -> None:
        _forbidden(self)
        for name in (
            "edge_token",
            "from_kind",
            "from_token",
            "to_kind",
            "to_token",
            "edge_kind",
            "recipe_id",
        ):
            _stable(name, getattr(self, name))
        object.__setattr__(self, "window_index", _window(self.window_index))
        for name in (
            "observed_count",
            "completed_count",
            "share_milli",
            "created_elsewhere_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class SupplyChainRecord:
    chain_token: str
    window_index: int
    stage_tokens: tuple[str, ...]
    edge_tokens: tuple[str, ...]
    depth: int
    completed_count: int
    coverage: str

    def __post_init__(self) -> None:
        _forbidden(self)
        _stable("chain_token", self.chain_token)
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "stage_tokens", _names(self.stage_tokens))
        object.__setattr__(self, "edge_tokens", _names(self.edge_tokens))
        for name in ("depth", "completed_count"):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class SupplyChainLineageRecord:
    chain_token: str
    window_index: int
    status: str
    predecessor_tokens: tuple[str, ...]
    successor_tokens: tuple[str, ...]
    shared_edge_count: int
    overlap_milli: int
    coverage: str

    def __post_init__(self) -> None:
        _forbidden(self)
        _stable("chain_token", self.chain_token)
        object.__setattr__(self, "window_index", _window(self.window_index))
        if self.status not in _STATUSES:
            raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_status")
        object.__setattr__(self, "predecessor_tokens", _names(self.predecessor_tokens))
        object.__setattr__(self, "successor_tokens", _names(self.successor_tokens))
        for name in ("shared_edge_count", "overlap_milli"):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class SupplyBottleneckRecord:
    bottleneck_token: str
    window_index: int
    kind: str
    stage_token: str
    edge_token: str
    observed_count: int
    demand_count: int
    supply_count: int
    ratio_milli: int
    location_token: str
    organization_token: str
    skill_domain: str
    coverage: str

    def __post_init__(self) -> None:
        _forbidden(self)
        for name in (
            "bottleneck_token",
            "kind",
            "stage_token",
            "edge_token",
            "location_token",
            "organization_token",
            "skill_domain",
        ):
            _stable(name, getattr(self, name))
        object.__setattr__(self, "window_index", _window(self.window_index))
        for name in (
            "observed_count",
            "demand_count",
            "supply_count",
            "ratio_milli",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class SupplyLocationRecord:
    location_token: str
    window_index: int
    observed_count: int
    completed_count: int
    coverage: str

    def __post_init__(self) -> None:
        _forbidden(self)
        _stable("location_token", self.location_token)
        object.__setattr__(self, "window_index", _window(self.window_index))
        for name in ("observed_count", "completed_count"):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class SupplyOrganizationRecord:
    organization_token: str
    window_index: int
    actor_count: int
    claim_count: int
    completed_count: int
    coverage: str

    def __post_init__(self) -> None:
        _forbidden(self)
        _stable("organization_token", self.organization_token)
        object.__setattr__(self, "window_index", _window(self.window_index))
        for name in ("actor_count", "claim_count", "completed_count"):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class SupplyChainSummaryRecord:
    window_tick: int
    stage_count: int
    edge_count: int
    chain_count: int
    lineage_count: int
    bottleneck_count: int
    location_count: int
    organization_count: int
    sustained_chain_count: int
    max_depth: int
    coverage: str
    truncated: bool

    def __post_init__(self) -> None:
        _forbidden(self)
        for name in (
            "window_tick",
            "stage_count",
            "edge_count",
            "chain_count",
            "lineage_count",
            "bottleneck_count",
            "location_count",
            "organization_count",
            "sustained_chain_count",
            "max_depth",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _coverage(self.coverage)
        if type(self.truncated) is not bool:
            raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_value")


@dataclass(frozen=True, slots=True)
class SupplyChainSnapshot:
    run_id: str
    schema_version: str
    policy_version: str
    summary: SupplyChainSummaryRecord
    stages: tuple[SupplyStageRecord, ...] = ()
    edges: tuple[SupplyDependencyRecord, ...] = ()
    chains: tuple[SupplyChainRecord, ...] = ()
    lineage: tuple[SupplyChainLineageRecord, ...] = ()
    bottlenecks: tuple[SupplyBottleneckRecord, ...] = ()
    locations: tuple[SupplyLocationRecord, ...] = ()
    organizations: tuple[SupplyOrganizationRecord, ...] = ()
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        _forbidden(self)
        _stable("run_id", self.run_id)
        if self.schema_version != SUPPLY_CHAIN_SNAPSHOT_VERSION:
            raise SupplyChainSnapshotError("supply_chain_snapshot_version_unsupported")
        if self.policy_version != SUPPLY_CHAIN_SNAPSHOT_POLICY:
            raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_policy")
        if type(self.summary) is not SupplyChainSummaryRecord:
            raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_summary")
        for name, cap, row_type in (
            ("stages", MAX_SUPPLY_SNAPSHOT_STAGES, SupplyStageRecord),
            ("edges", MAX_SUPPLY_SNAPSHOT_EDGES, SupplyDependencyRecord),
            ("chains", MAX_SUPPLY_SNAPSHOT_CHAINS, SupplyChainRecord),
            ("lineage", MAX_SUPPLY_SNAPSHOT_LINEAGE, SupplyChainLineageRecord),
            (
                "bottlenecks",
                MAX_SUPPLY_SNAPSHOT_BOTTLENECKS,
                SupplyBottleneckRecord,
            ),
            ("locations", MAX_SUPPLY_SNAPSHOT_LOCATIONS, SupplyLocationRecord),
            (
                "organizations",
                MAX_SUPPLY_SNAPSHOT_ORGANIZATIONS,
                SupplyOrganizationRecord,
            ),
        ):
            rows = getattr(self, name)
            if type(rows) is not tuple or any(
                type(item) is not row_type for item in rows
            ):
                raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_rows")
            if len(rows) > cap:
                raise SupplyChainSnapshotError("supply_chain_snapshot_cap_exceeded")
        if type(self.digest) is not str or (self.digest and len(self.digest) != 64):
            raise SupplyChainSnapshotError("supply_chain_snapshot_invalid_digest")
        if type(self.publication_id) is not str:
            raise SupplyChainSnapshotError(
                "supply_chain_snapshot_invalid_publication_id"
            )


def empty_supply_chain_snapshot(
    run_id: str, *, window_tick: int = 0
) -> SupplyChainSnapshot:
    return SupplyChainSnapshot(
        run_id=_stable("run_id", run_id),
        schema_version=SUPPLY_CHAIN_SNAPSHOT_VERSION,
        policy_version=SUPPLY_CHAIN_SNAPSHOT_POLICY,
        summary=SupplyChainSummaryRecord(
            window_tick=window_tick,
            stage_count=0,
            edge_count=0,
            chain_count=0,
            lineage_count=0,
            bottleneck_count=0,
            location_count=0,
            organization_count=0,
            sustained_chain_count=0,
            max_depth=0,
            coverage="missing",
            truncated=False,
        ),
    )
