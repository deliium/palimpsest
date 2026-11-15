"""Canonical sibling document for completed-run economic cascades."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from world.identifiers import require_stable_id

__all__ = [
    "ECONOMIC_CASCADES_POLICY_VERSION",
    "ECONOMIC_CASCADES_PUBLICATION_PREFIX",
    "ECONOMIC_CASCADES_SNAPSHOT_VERSION",
    "MAX_ECONOMIC_CASCADES_CHAIN_ROWS",
    "MAX_ECONOMIC_CASCADES_SNAPSHOT_BYTES",
    "MAX_ECONOMIC_CASCADES_STATUS_ROWS",
    "EconomicCascadeChainRecord",
    "EconomicCascadeCoverageRecord",
    "EconomicCascadeDependencyRecord",
    "EconomicCascadeDisruptionRecord",
    "EconomicCascadePropagationRecord",
    "EconomicCascadeSummaryRecord",
    "EconomicCascadesSnapshot",
    "empty_economic_cascades_snapshot",
]

ECONOMIC_CASCADES_SNAPSHOT_VERSION: Final[str] = "economic-cascades-snapshot-v1"
ECONOMIC_CASCADES_POLICY_VERSION: Final[str] = "economic-cascades.v1"
ECONOMIC_CASCADES_PUBLICATION_PREFIX: Final[str] = "ecasc-"
MAX_ECONOMIC_CASCADES_STATUS_ROWS: Final[int] = 1_024
MAX_ECONOMIC_CASCADES_CHAIN_ROWS: Final[int] = 2_048
MAX_ECONOMIC_CASCADES_SNAPSHOT_BYTES: Final[int] = 8_388_608
MAX_ECONOMIC_CASCADES_WINDOW_INDEX: Final[int] = 511

_DISRUPTION_KINDS = frozenset(
    {
        "resource_loss",
        "route_closure",
        "infrastructure_destruction",
        "population_loss",
        "tool_shortage",
    }
)
_DEPENDENCY_KINDS = frozenset(
    {
        "resource_input",
        "item_input",
        "tool_dependency",
        "infrastructure_dependency",
        "transport_dependency",
    }
)
_CHAIN_STATES = frozenset({"linked", "unlinked", "unresolved", "unavailable"})
_COVERAGE = frozenset({"complete", "partial", "missing"})
_AVAILABILITY = frozenset(
    {"available", "insufficient_samples", "unavailable"}
)


def _fail() -> ValueError:
    return ValueError("economic_cascades_snapshot_invalid")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise _fail()
    return value


def _share(value: object) -> int:
    number = _count(value)
    if number > 1_000:
        raise _fail()
    return number


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise _fail()
    return require_stable_id("token", value)


def _window(value: object) -> int:
    number = _count(value)
    if number > MAX_ECONOMIC_CASCADES_WINDOW_INDEX:
        raise _fail()
    return number


def _enum(value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise _fail()
    return value


@dataclass(frozen=True, slots=True)
class EconomicCascadeSummaryRecord:
    window_tick: int
    window_count: int
    coverage: str
    availability: str
    event_count: int
    disruption_count: int
    stage_count: int
    dependency_edge_count: int
    chain_count: int
    linked_chain_count: int
    disruption_kind_count: int
    max_depth: int

    def __post_init__(self) -> None:
        for name in (
            "window_tick",
            "window_count",
            "event_count",
            "disruption_count",
            "stage_count",
            "dependency_edge_count",
            "chain_count",
            "linked_chain_count",
            "disruption_kind_count",
            "max_depth",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class EconomicCascadeDisruptionRecord:
    window_index: int
    window_tick: int
    kind: str
    disruption_count: int
    magnitude_total: int
    subject_count: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(self, "kind", _enum(self.kind, _DISRUPTION_KINDS))
        for name in (
            "disruption_count",
            "magnitude_total",
            "subject_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class EconomicCascadeDependencyRecord:
    window_index: int
    window_tick: int
    upstream_token: str
    downstream_recipe_token: str
    kind: str
    depth: int
    evidence_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(self, "upstream_token", _token(self.upstream_token))
        object.__setattr__(
            self, "downstream_recipe_token", _token(self.downstream_recipe_token)
        )
        object.__setattr__(self, "kind", _enum(self.kind, _DEPENDENCY_KINDS))
        depth = _count(self.depth)
        if depth < 1:
            raise _fail()
        object.__setattr__(self, "depth", depth)
        object.__setattr__(self, "evidence_count", _count(self.evidence_count))


@dataclass(frozen=True, slots=True)
class EconomicCascadeChainRecord:
    chain_token: str
    window_index: int
    window_tick: int
    disruption_kind: str
    depth: int
    lag_windows: int
    shortfall_share_milli: int
    state: str
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_token", _token(self.chain_token))
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(
            self,
            "disruption_kind",
            _enum(self.disruption_kind, _DISRUPTION_KINDS),
        )
        depth = _count(self.depth)
        if depth < 1:
            raise _fail()
        object.__setattr__(self, "depth", depth)
        object.__setattr__(self, "lag_windows", _count(self.lag_windows))
        object.__setattr__(
            self,
            "shortfall_share_milli",
            _share(self.shortfall_share_milli),
        )
        object.__setattr__(self, "state", _enum(self.state, _CHAIN_STATES))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))


@dataclass(frozen=True, slots=True)
class EconomicCascadePropagationRecord:
    window_index: int
    window_tick: int
    disruption_kind: str
    chain_count: int
    linked_chain_count: int
    unlinked_chain_count: int
    unresolved_chain_count: int
    mean_depth_milli: int
    mean_lag_milli: int
    downstream_stage_count: int
    coverage: str
    availability: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        object.__setattr__(self, "window_tick", _count(self.window_tick))
        object.__setattr__(
            self,
            "disruption_kind",
            _enum(self.disruption_kind, _DISRUPTION_KINDS),
        )
        for name in (
            "chain_count",
            "linked_chain_count",
            "unlinked_chain_count",
            "unresolved_chain_count",
            "mean_depth_milli",
            "mean_lag_milli",
            "downstream_stage_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class EconomicCascadeCoverageRecord:
    window_index: int
    window_tick: int
    window_count: int
    event_count: int
    disruption_count: int
    stage_count: int
    dependency_edge_count: int
    labor_join_count: int
    chain_count: int
    linked_chain_count: int
    truncated: bool
    coverage: str
    availability: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_index", _window(self.window_index))
        for name in (
            "window_tick",
            "window_count",
            "event_count",
            "disruption_count",
            "stage_count",
            "dependency_edge_count",
            "labor_join_count",
            "chain_count",
            "linked_chain_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if type(self.truncated) is not bool:
            raise _fail()
        object.__setattr__(self, "coverage", _enum(self.coverage, _COVERAGE))
        object.__setattr__(
            self, "availability", _enum(self.availability, _AVAILABILITY)
        )


@dataclass(frozen=True, slots=True)
class EconomicCascadesSnapshot:
    snapshot_version: str
    policy_version: str
    run_id: str
    generated_from_tick: int
    summary: EconomicCascadeSummaryRecord
    disruptions: tuple[EconomicCascadeDisruptionRecord, ...] = ()
    dependencies: tuple[EconomicCascadeDependencyRecord, ...] = ()
    chains: tuple[EconomicCascadeChainRecord, ...] = ()
    propagation: tuple[EconomicCascadePropagationRecord, ...] = ()
    coverage: tuple[EconomicCascadeCoverageRecord, ...] = ()
    internal_digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        if self.snapshot_version != ECONOMIC_CASCADES_SNAPSHOT_VERSION:
            raise ValueError("economic_cascades_snapshot_version")
        if self.policy_version != ECONOMIC_CASCADES_POLICY_VERSION:
            raise ValueError("economic_cascades_snapshot_version")
        object.__setattr__(
            self, "generated_from_tick", _count(self.generated_from_tick)
        )
        if type(self.summary) is not EconomicCascadeSummaryRecord:
            raise _fail()
        for name, row_type, cap in (
            (
                "disruptions",
                EconomicCascadeDisruptionRecord,
                MAX_ECONOMIC_CASCADES_STATUS_ROWS,
            ),
            (
                "dependencies",
                EconomicCascadeDependencyRecord,
                MAX_ECONOMIC_CASCADES_STATUS_ROWS,
            ),
            (
                "chains",
                EconomicCascadeChainRecord,
                MAX_ECONOMIC_CASCADES_CHAIN_ROWS,
            ),
            (
                "propagation",
                EconomicCascadePropagationRecord,
                MAX_ECONOMIC_CASCADES_STATUS_ROWS,
            ),
            (
                "coverage",
                EconomicCascadeCoverageRecord,
                MAX_ECONOMIC_CASCADES_STATUS_ROWS,
            ),
        ):
            values = getattr(self, name)
            if type(values) is not tuple or len(values) > cap:
                raise _fail()
            for row in values:
                if type(row) is not row_type:
                    raise _fail()
        if type(self.internal_digest) is not str:
            raise _fail()
        if type(self.publication_id) is not str:
            raise _fail()


def empty_economic_cascades_snapshot(
    run_id: str,
) -> EconomicCascadesSnapshot:
    """Return one empty missing-coverage snapshot."""

    return EconomicCascadesSnapshot(
        snapshot_version=ECONOMIC_CASCADES_SNAPSHOT_VERSION,
        policy_version=ECONOMIC_CASCADES_POLICY_VERSION,
        run_id=run_id,
        generated_from_tick=0,
        summary=EconomicCascadeSummaryRecord(
            window_tick=0,
            window_count=0,
            coverage="missing",
            availability="unavailable",
            event_count=0,
            disruption_count=0,
            stage_count=0,
            dependency_edge_count=0,
            chain_count=0,
            linked_chain_count=0,
            disruption_kind_count=0,
            max_depth=0,
        ),
    )
