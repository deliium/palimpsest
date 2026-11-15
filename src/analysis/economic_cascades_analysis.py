"""Single bounded economic-cascade analysis value."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.economic_cascades_chains import link_economic_cascade_chains
from analysis.economic_cascades_contract import (
    ECONOMIC_CASCADES_POLICY_VERSION,
    CascadeAvailability,
    CascadeCoverage,
    CascadeLayer,
    EconomicCascadesError,
    assert_economic_cascade_layer_separation,
)
from analysis.economic_cascades_dependencies import (
    build_economic_cascade_dependencies,
)
from analysis.economic_cascades_detection import detect_economic_cascade_episodes
from analysis.economic_cascades_events import harvest_economic_cascade_disruptions
from analysis.economic_cascades_policy import (
    EconomicCascadesPolicy,
    default_policy,
    window_tick,
)
from analysis.economic_cascades_rows import (
    CascadeChainRow,
    CascadeCoverageRow,
    CascadeDependencyEdgeRow,
    CascadeDisruptionRow,
    CascadeEpisodeRow,
    CascadePropagationRow,
    CascadeStageRow,
)
from analysis.supply_chain_events import (
    SupplyRecipeSpec,
    SupplyStageObservation,
    supply_evidence_from_events,
)
from analysis.supply_chain_policy import default_supply_chain_analysis_policy
from world.events import WorldEvent

__all__ = [
    "EconomicCascadesAnalysis",
    "economic_cascades_analysis_digest",
    "empty_economic_cascades_analysis",
    "harvest_economic_cascades_analysis",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.economic_cascades.analysis")


@dataclass(frozen=True, slots=True)
class EconomicCascadesAnalysis:
    """Immutable bounded evidence plus analytical rows."""

    policy_version: str
    window_tick: int
    window_count: int
    coverage: CascadeCoverage
    evidence_coverage: CascadeCoverage
    chain_coverage: CascadeCoverage
    disruptions: tuple[CascadeDisruptionRow, ...]
    episodes: tuple[CascadeEpisodeRow, ...]
    stages: tuple[CascadeStageRow, ...]
    edges: tuple[CascadeDependencyEdgeRow, ...]
    chains: tuple[CascadeChainRow, ...]
    propagation_rows: tuple[CascadePropagationRow, ...]
    coverage_row: CascadeCoverageRow
    notices: tuple[str, ...]
    event_count: int
    disruption_count: int
    stage_count: int
    dependency_edge_count: int
    labor_join_count: int
    chain_count: int
    linked_chain_count: int
    unlinked_chain_count: int
    unresolved_chain_count: int
    disruption_kind_count: int
    max_depth: int

    def __post_init__(self) -> None:
        if self.policy_version != ECONOMIC_CASCADES_POLICY_VERSION:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        for name in (
            "disruptions",
            "episodes",
            "stages",
            "edges",
            "chains",
            "propagation_rows",
            "notices",
        ):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicCascadesError("economic_cascades_invalid_chain")
        for coverage in (
            self.coverage,
            self.evidence_coverage,
            self.chain_coverage,
        ):
            if type(coverage) is not CascadeCoverage:
                raise EconomicCascadesError("economic_cascades_invalid_chain")
        if type(self.coverage_row) is not CascadeCoverageRow:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
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
            "unlinked_chain_count",
            "unresolved_chain_count",
            "disruption_kind_count",
            "max_depth",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicCascadesError("economic_cascades_invalid_chain")
        if self.coverage is CascadeCoverage.MISSING and any(
            (
                self.disruptions,
                self.episodes,
                self.stages,
                self.edges,
                self.chains,
                self.propagation_rows,
            )
        ):
            raise EconomicCascadesError("economic_cascades_invalid_chain")

    @property
    def row_count(self) -> int:
        return (
            len(self.disruptions)
            + len(self.episodes)
            + len(self.stages)
            + len(self.edges)
            + len(self.chains)
            + len(self.propagation_rows)
        )

    @property
    def source_layers(self) -> tuple[CascadeLayer, ...]:
        return (
            CascadeLayer.OBJECTIVE_DISRUPTION,
            CascadeLayer.DEPENDENCY_STRUCTURE,
            CascadeLayer.ANALYTICAL_CHAIN,
        )


def empty_economic_cascades_analysis(
    policy: EconomicCascadesPolicy | None = None,
) -> EconomicCascadesAnalysis:
    """Return the explicit no-evidence value."""

    coverage_row = CascadeCoverageRow(
        window_index=0,
        window_tick=0,
        window_count=0,
        event_count=0,
        disruption_count=0,
        stage_count=0,
        dependency_edge_count=0,
        labor_join_count=0,
        chain_count=0,
        linked_chain_count=0,
        truncated=False,
        coverage=CascadeCoverage.MISSING,
        availability=CascadeAvailability.UNAVAILABLE,
    )
    return EconomicCascadesAnalysis(
        policy_version=ECONOMIC_CASCADES_POLICY_VERSION,
        window_tick=0,
        window_count=0,
        coverage=CascadeCoverage.MISSING,
        evidence_coverage=CascadeCoverage.MISSING,
        chain_coverage=CascadeCoverage.MISSING,
        disruptions=(),
        episodes=(),
        stages=(),
        edges=(),
        chains=(),
        propagation_rows=(),
        coverage_row=coverage_row,
        notices=(),
        event_count=0,
        disruption_count=0,
        stage_count=0,
        dependency_edge_count=0,
        labor_join_count=0,
        chain_count=0,
        linked_chain_count=0,
        unlinked_chain_count=0,
        unresolved_chain_count=0,
        disruption_kind_count=0,
        max_depth=0,
    )


def economic_cascades_analysis_digest(
    analysis: EconomicCascadesAnalysis,
) -> str:
    """Return a content-addressed digest over counts and notices only."""

    if type(analysis) is not EconomicCascadesAnalysis:
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    material = "\x1f".join(
        (
            analysis.policy_version,
            str(analysis.window_tick),
            str(analysis.window_count),
            analysis.coverage.value,
            analysis.evidence_coverage.value,
            analysis.chain_coverage.value,
            str(len(analysis.disruptions)),
            str(len(analysis.episodes)),
            str(len(analysis.stages)),
            str(len(analysis.edges)),
            str(len(analysis.chains)),
            str(len(analysis.propagation_rows)),
            str(analysis.linked_chain_count),
            str(analysis.unlinked_chain_count),
            str(analysis.unresolved_chain_count),
            ",".join(analysis.notices),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _merge_notices(
    values: Sequence[Sequence[str]], policy: EconomicCascadesPolicy
) -> tuple[str, ...]:
    merged: set[str] = set()
    for group in values:
        merged.update(group)
    ordered = sorted(merged)
    return tuple(ordered[: policy.max_notices])


def harvest_economic_cascades_analysis(
    *,
    events: Sequence[WorldEvent],
    recipe_specs: Sequence[SupplyRecipeSpec],
    stages: Sequence[SupplyStageObservation] | None = None,
    infrastructure: Sequence[tuple[str, str, bool]] = (),
    routes: Sequence[tuple[str, str, str]] = (),
    labor_joins: Sequence[tuple[str, tuple[str, ...]]] = (),
    policy: EconomicCascadesPolicy | None = None,
    window_end: int | None = None,
) -> EconomicCascadesAnalysis:
    """Compose the single bounded analysis from committed evidence."""

    active = default_policy() if policy is None else policy
    if type(active) is not EconomicCascadesPolicy:
        raise EconomicCascadesError("economic_cascades_invalid_policy")
    if events is None or not isinstance(events, Sequence):
        raise EconomicCascadesError("economic_cascades_invalid_event_order")
    if isinstance(recipe_specs, (str, bytes)) or not isinstance(
        recipe_specs, Sequence
    ):
        raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
    if not events or not recipe_specs:
        _LOG.debug("economic_cascades_analysis_empty")
        return empty_economic_cascades_analysis(active)

    if window_end is not None:
        if isinstance(window_end, bool) or type(window_end) is not int:
            raise EconomicCascadesError("economic_cascades_invalid_event_order")
        events = tuple(
            event
            for event in events
            if isinstance(getattr(event, "tick", None), int)
            and event.tick <= window_end
        )
        if not events:
            return empty_economic_cascades_analysis(active)

    if stages is None:
        harvest = supply_evidence_from_events(
            events,
            policy=default_supply_chain_analysis_policy(),
            recipes=recipe_specs,
            skill_levels=(),
            infrastructure=(),
            organization_claims=(),
        )
        stage_observations = harvest.rows
    else:
        stage_observations = tuple(stages)

    if window_end is not None:
        stage_observations = tuple(
            row
            for row in stage_observations
            if row.window_index * active.window_ticks <= window_end
        )

    disruptions = harvest_economic_cascade_disruptions(events, policy=active)
    dependencies = build_economic_cascade_dependencies(
        stages=stage_observations,
        recipes=recipe_specs,
        infrastructure=infrastructure,
        routes=routes,
        policy=active,
    )
    joins = tuple(labor_joins) if labor_joins else dependencies.labor_joins
    detection = detect_economic_cascade_episodes(
        disruptions=disruptions.rows,
        stages=dependencies.stage_rows,
        policy=active,
    )
    chains = link_economic_cascade_chains(
        episodes=detection.episodes,
        disruptions=disruptions.rows,
        stages=detection.stage_rows,
        edges=dependencies.edges,
        labor_joins=joins,
        policy=active,
    )

    notes = _merge_notices(
        (
            disruptions.notices,
            dependencies.notices,
            detection.notices,
            chains.notices,
        ),
        active,
    )
    truncated = len(
        set(
            disruptions.notices
            + dependencies.notices
            + detection.notices
            + chains.notices
        )
    ) > len(notes)

    surviving_windows: set[int] = set()
    for episode_row in detection.episodes:
        surviving_windows.add(episode_row.window_index)
    for stage_row in dependencies.stage_rows:
        surviving_windows.add(stage_row.window_index)
    for edge_row in dependencies.edges:
        surviving_windows.add(edge_row.window_index)
    for chain_row in chains.chains:
        surviving_windows.add(chain_row.window_index)
    for propagation_row in chains.propagation_rows:
        surviving_windows.add(propagation_row.window_index)
    windows = sorted(surviving_windows)
    window_count = len(windows)
    latest_window = windows[-1] if windows else 0
    if window_count > active.max_windows:
        window_count = active.max_windows
        notes = tuple(dict.fromkeys((*notes, "windows_truncated")))[
            : active.max_notices
        ]
        truncated = True

    coverage_values = [
        disruptions.coverage,
        dependencies.coverage,
        detection.coverage,
        chains.coverage,
    ]
    if not any(
        (
            disruptions.rows,
            detection.episodes,
            dependencies.stage_rows,
            dependencies.edges,
            chains.chains,
        )
    ):
        coverage = CascadeCoverage.MISSING
    elif (
        truncated
        or notes
        or any(value is CascadeCoverage.PARTIAL for value in coverage_values)
    ):
        coverage = CascadeCoverage.PARTIAL
    else:
        coverage = CascadeCoverage.COMPLETE

    coverage_row = CascadeCoverageRow(
        window_index=latest_window,
        window_tick=window_tick(latest_window, active),
        window_count=window_count,
        event_count=disruptions.event_count,
        disruption_count=len(detection.episodes),
        stage_count=len(dependencies.stage_rows),
        dependency_edge_count=len(dependencies.edges),
        labor_join_count=len(joins),
        chain_count=len(chains.chains),
        linked_chain_count=chains.linked_count,
        truncated=truncated,
        coverage=coverage,
        availability=(
            CascadeAvailability.AVAILABLE
            if chains.linked_count >= active.min_linked_chains
            else (
                CascadeAvailability.INSUFFICIENT_SAMPLES
                if chains.linked_count > 0
                else CascadeAvailability.UNAVAILABLE
            )
        ),
    )

    assert_economic_cascade_layer_separation(
        objective_rows=(*disruptions.rows, *dependencies.stage_rows),
        dependency_rows=dependencies.edges,
        analytical_rows=(
            *detection.episodes,
            *chains.chains,
            *chains.propagation_rows,
        ),
    )

    analysis = EconomicCascadesAnalysis(
        policy_version=ECONOMIC_CASCADES_POLICY_VERSION,
        window_tick=window_tick(latest_window, active),
        window_count=window_count,
        coverage=coverage,
        evidence_coverage=disruptions.coverage,
        chain_coverage=chains.coverage,
        disruptions=disruptions.rows,
        episodes=detection.episodes,
        stages=dependencies.stage_rows,
        edges=dependencies.edges,
        chains=chains.chains,
        propagation_rows=chains.propagation_rows,
        coverage_row=coverage_row,
        notices=notes,
        event_count=disruptions.event_count,
        disruption_count=len(detection.episodes),
        stage_count=len(dependencies.stage_rows),
        dependency_edge_count=len(dependencies.edges),
        labor_join_count=len(joins),
        chain_count=len(chains.chains),
        linked_chain_count=chains.linked_count,
        unlinked_chain_count=chains.unlinked_count,
        unresolved_chain_count=chains.unresolved_count,
        disruption_kind_count=len(
            {row.kind for row in detection.episodes}
        ),
        max_depth=chains.max_depth,
    )
    _LOG.debug(
        "economic_cascades_analysis_layers objective=%s dependency=%s analytical=%s",
        len(disruptions.rows) + len(dependencies.stage_rows),
        len(dependencies.edges),
        len(detection.episodes) + len(chains.chains) + len(chains.propagation_rows),
    )
    _LOG.info(
        "economic_cascades_analysis_complete windows=%s rows=%s",
        analysis.window_count,
        analysis.row_count,
    )
    if coverage is CascadeCoverage.PARTIAL:
        _LOG.warning("economic_cascades_partial_coverage")
    return analysis
