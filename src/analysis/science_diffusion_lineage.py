"""Detached scientific-knowledge diffusion fold.

The fold consumes only neutral rows. It never imports cognition, live services,
API, persistence, or clients, and it never returns a command. Analytical edges,
changed representations, losses, and rediscoveries are descriptive results, not
truth or authority.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from typing import Final

from analysis.science_diffusion_contract import (
    DIFFUSION_WINDOW_TICKS,
    DiffusionError,
    DiffusionInputs,
    DiffusionLane,
    DiffusionOccurrence,
    DiffusionReason,
    DiffusionResolution,
    DiffusionStage,
    LaneCoverageState,
    ScienceVersion,
    ScienceVersionKey,
    compare_science_versions,
)

__all__ = [
    "CarrierClosureWitness",
    "DiffusionAssessment",
    "DiffusionChange",
    "DiffusionChangeKind",
    "DiffusionEdge",
    "DiffusionEdgeKind",
    "DiffusionLoss",
    "DiffusionLossScope",
    "DiffusionRediscovery",
    "DiffusionRediscoveryKind",
    "DiffusionTransmission",
    "DiffusionWindow",
    "RediscoveryRoot",
    "V3Link",
    "derive_science_diffusion",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.science_diffusion_lineage")


class DiffusionEdgeKind(StrEnum):
    DELIVERED = "delivered"
    INTERPRETED = "interpreted"
    ADOPTED = "adopted"
    LOCALLY_DERIVED = "locally_derived"
    REPORTED_REFERENCE = "reported_reference"
    CARRIED = "carried"
    REVISED = "revised"


_STAGE_EDGE: Final[dict[DiffusionStage, DiffusionEdgeKind]] = {
    DiffusionStage.DELIVERED: DiffusionEdgeKind.DELIVERED,
    DiffusionStage.INTERPRETED: DiffusionEdgeKind.INTERPRETED,
    DiffusionStage.ADOPTED: DiffusionEdgeKind.ADOPTED,
    DiffusionStage.LOCALLY_DERIVED: DiffusionEdgeKind.LOCALLY_DERIVED,
    DiffusionStage.REPORTED_REFERENCE: DiffusionEdgeKind.REPORTED_REFERENCE,
    DiffusionStage.CARRIED: DiffusionEdgeKind.CARRIED,
}

_DEDUP_EDGE_KINDS: Final[frozenset[DiffusionEdgeKind]] = frozenset(
    {
        DiffusionEdgeKind.ADOPTED,
        DiffusionEdgeKind.LOCALLY_DERIVED,
        DiffusionEdgeKind.REVISED,
    }
)


class DiffusionChangeKind(StrEnum):
    MUTATION = "mutation"
    MISUNDERSTANDING = "misunderstanding"
    TRANSLATION = "translation"


class DiffusionLossScope(StrEnum):
    OWNER_VERSION = "owner_version"
    PHYSICAL_CARRIER = "physical_carrier"
    OBSERVED_LINEAGE = "observed_lineage"


class DiffusionRediscoveryKind(StrEnum):
    REACQUIRED = "reacquired"
    INDEPENDENT = "independent"


@dataclass(frozen=True, slots=True)
class V3Link:
    """Neutral view of one existing knowledge-genealogy link."""

    transmission_key: str
    v3_node_key: str
    origin: str
    relation: str
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class CarrierClosureWitness:
    """Explicit closure of known holders and carriers after a loss."""

    witness_boundary: int
    holders_closed: bool
    carriers_closed: bool
    version_key: ScienceVersionKey | None = None
    carrier_key: str = ""

    def __post_init__(self) -> None:
        if self.witness_boundary < 0:
            raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)


@dataclass(frozen=True, slots=True)
class RediscoveryRoot:
    """An affirmative committed local root evidenced at formation."""

    version_key: ScienceVersionKey
    root_kind: str
    root_ref: str
    affirmative: bool
    committed: bool

    def __post_init__(self) -> None:
        if not self.root_kind or not self.root_ref:
            raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)


@dataclass(frozen=True, slots=True)
class DiffusionWindow:
    """One absolute 32-tick coverage window."""

    window_index: int
    start_tick: int
    end_tick_exclusive: int
    complete: bool
    lane_states: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.end_tick_exclusive <= self.start_tick:
            raise DiffusionError(DiffusionReason.MALFORMED_EVIDENCE.value)

    def complete_for(self, lanes: tuple[DiffusionLane, ...]) -> bool:
        states = dict(self.lane_states)
        return all(states.get(lane.value) == "complete" for lane in lanes)


@dataclass(frozen=True, slots=True)
class DiffusionTransmission:
    """One countable carrier occurrence, including repeated exposures."""

    transmission_key: str
    lane: str
    stage: str
    tick: int
    actor_id: str | None
    counterparty_id: str | None
    source_version: ScienceVersionKey | None
    target_version: ScienceVersionKey | None
    carrier_id: str | None
    content_revision: int | None
    context_flags: tuple[str, ...]
    resolution: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class DiffusionEdge:
    """One deduplicated forward evidence edge."""

    edge_key: str
    kind: DiffusionEdgeKind
    source_version: ScienceVersionKey | None
    target_version: ScienceVersionKey | None
    recipient_owner: str | None
    first_tick: int
    first_witness: str
    occurrence_count: int = 1


@dataclass(frozen=True, slots=True)
class DiffusionChange:
    """One witnessed representation change or translation use."""

    change_key: str
    kind: DiffusionChangeKind
    from_version: ScienceVersionKey | None
    to_version: ScienceVersionKey | None
    carrier_id: str | None
    confirmation_boundary: int
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiffusionLoss:
    """One scoped loss witness, optionally confirmed analytical lineage loss."""

    loss_key: str
    scope: DiffusionLossScope
    version_key: ScienceVersionKey | None
    carrier_id: str | None
    witness_tick: int
    witness_boundary: int
    confirmed: bool
    confirmation_boundary: int | None = None


@dataclass(frozen=True, slots=True)
class DiffusionRediscovery:
    """One reacquisition or independent rediscovery after confirmation."""

    rediscovery_key: str
    kind: DiffusionRediscoveryKind
    version_key: ScienceVersionKey
    root_kind: str
    root_ref: str
    confirmation_boundary: int


@dataclass(frozen=True, slots=True)
class DiffusionAssessment:
    """Complete detached assessment for one bounded diffusion input."""

    run_id: str
    windows: tuple[DiffusionWindow, ...]
    transmissions: tuple[DiffusionTransmission, ...]
    edges: tuple[DiffusionEdge, ...]
    changes: tuple[DiffusionChange, ...]
    losses: tuple[DiffusionLoss, ...]
    rediscoveries: tuple[DiffusionRediscovery, ...]
    v3_links: tuple[V3Link, ...]
    diagnostics: tuple[str, ...]
    origin_unresolved: int
    convergence_candidates: int

    @property
    def confirmed_losses(self) -> tuple[DiffusionLoss, ...]:
        return tuple(row for row in self.losses if row.confirmed)

    def transmissions_for_stage(
        self, stage: DiffusionStage
    ) -> tuple[DiffusionTransmission, ...]:
        return tuple(row for row in self.transmissions if row.stage == stage.value)


def _transmission_key(occurrence: DiffusionOccurrence) -> str:
    return repr(occurrence.evidence.qualified_key())


def _transmission_rows(
    occurrences: tuple[DiffusionOccurrence, ...],
) -> tuple[DiffusionTransmission, ...]:
    rows: list[DiffusionTransmission] = []
    for occurrence in occurrences:
        rows.append(
            DiffusionTransmission(
                transmission_key=_transmission_key(occurrence),
                lane=occurrence.lane.value,
                stage=occurrence.stage.value,
                tick=occurrence.tick,
                actor_id=occurrence.actor_id,
                counterparty_id=occurrence.counterparty_id,
                source_version=occurrence.source_version,
                target_version=occurrence.target_version,
                carrier_id=occurrence.carrier_id,
                content_revision=occurrence.content_revision,
                context_flags=tuple(flag.value for flag in occurrence.context_flags),
                resolution=occurrence.resolution.value,
                reason=None if occurrence.reason is None else occurrence.reason.value,
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.tick,
                row.lane,
                row.transmission_key,
                row.stage,
            ),
        )
    )


def _edge_key(
    kind: DiffusionEdgeKind,
    source: ScienceVersionKey | None,
    target: ScienceVersionKey | None,
    recipient: str | None,
    carrier: str | None,
) -> str:
    parts = (
        kind.value,
        "" if source is None else repr(source.as_tuple()),
        "" if target is None else repr(target.as_tuple()),
        recipient or "",
        carrier or "",
    )
    return "\x1f".join(parts)


def _edge_rows(
    occurrences: tuple[DiffusionOccurrence, ...],
) -> tuple[tuple[DiffusionEdge, ...], tuple[str, ...]]:
    grouped: dict[str, DiffusionEdge] = {}
    diagnostics: list[str] = []
    for occurrence in occurrences:
        if occurrence.resolution is DiffusionResolution.EXCLUDED:
            continue
        kind = _STAGE_EDGE[occurrence.stage]
        source = occurrence.source_version
        target = occurrence.target_version
        if (
            occurrence.lane is DiffusionLane.SPEECH
            and occurrence.stage is DiffusionStage.ADOPTED
            and target is None
        ):
            # An adoption without a recorded target is exposure, not an edge.
            target = None
        key = _edge_key(
            kind, source, target, occurrence.counterparty_id, occurrence.carrier_id
        )
        prior = grouped.get(key)
        if prior is not None:
            grouped[key] = DiffusionEdge(
                edge_key=prior.edge_key,
                kind=prior.kind,
                source_version=prior.source_version,
                target_version=prior.target_version,
                recipient_owner=prior.recipient_owner,
                first_tick=prior.first_tick,
                first_witness=prior.first_witness,
                occurrence_count=prior.occurrence_count + 1,
            )
            continue
        grouped[key] = DiffusionEdge(
            edge_key=key,
            kind=kind,
            source_version=source,
            target_version=target,
            recipient_owner=occurrence.counterparty_id,
            first_tick=occurrence.tick,
            first_witness=_transmission_key(occurrence),
        )
    edges = tuple(
        sorted(
            grouped.values(),
            key=lambda row: (
                row.first_tick,
                row.kind.value,
                ""
                if row.source_version is None
                else repr(row.source_version.as_tuple()),
                ""
                if row.target_version is None
                else repr(row.target_version.as_tuple()),
                row.recipient_owner or "",
            ),
        )
    )
    _reject_backward_or_cyclic(edges, diagnostics)
    return edges, tuple(sorted(set(diagnostics)))


def _reject_backward_or_cyclic(
    edges: tuple[DiffusionEdge, ...], diagnostics: list[str]
) -> None:
    graph: dict[ScienceVersionKey, set[ScienceVersionKey]] = defaultdict(set)
    for edge in edges:
        if edge.source_version is None or edge.target_version is None:
            continue
        source = edge.source_version
        target = edge.target_version
        if source == target:
            continue
        if (
            source.kind is target.kind
            and source.owner_id == target.owner_id
            and source.local_id == target.local_id
            and target.revision_index <= source.revision_index
        ):
            diagnostics.append(DiffusionReason.SOURCE_NOT_PRIOR.value)
            continue
        graph[source].add(target)
    visiting: set[ScienceVersionKey] = set()
    visited: set[ScienceVersionKey] = set()

    def visit(node: ScienceVersionKey) -> bool:
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        for child in graph.get(node, ()):
            if not visit(child):
                return False
        visiting.discard(node)
        visited.add(node)
        return True

    for node in tuple(graph):
        if not visit(node):
            diagnostics.append(DiffusionReason.SOURCE_NOT_PRIOR.value)
            break


def _windows(inputs: DiffusionInputs) -> tuple[DiffusionWindow, ...]:
    end_tick = max(
        (
            max([row.end_tick_exclusive for row in inputs.coverage] or [0]),
            max([row.tick + 1 for row in inputs.occurrences] or [0]),
            max([row.occurrence_tick + 1 for row in inputs.versions] or [0]),
        )
    )
    if end_tick <= 0:
        return ()
    count = (end_tick + DIFFUSION_WINDOW_TICKS - 1) // DIFFUSION_WINDOW_TICKS
    windows: list[DiffusionWindow] = []
    for index in range(count):
        start = index * DIFFUSION_WINDOW_TICKS
        end = start + DIFFUSION_WINDOW_TICKS
        states: list[tuple[str, str]] = []
        complete = True
        for lane in DiffusionLane:
            state = _lane_window_state(inputs, lane, start, end)
            states.append((lane.value, state.value))
            if state is not LaneCoverageState.COMPLETE:
                complete = False
        windows.append(
            DiffusionWindow(
                window_index=index,
                start_tick=start,
                end_tick_exclusive=end,
                complete=complete,
                lane_states=tuple(states),
            )
        )
    return tuple(windows)


def _lane_window_state(
    inputs: DiffusionInputs, lane: DiffusionLane, start: int, end: int
) -> LaneCoverageState:
    rows = [
        row
        for row in inputs.coverage
        if row.lane is lane
        and row.start_tick <= start
        and row.end_tick_exclusive >= end
    ]
    if not rows:
        return LaneCoverageState.UNAVAILABLE
    if any(row.state is LaneCoverageState.UNAVAILABLE for row in rows):
        return LaneCoverageState.UNAVAILABLE
    if any(row.state is LaneCoverageState.PARTIAL for row in rows):
        return LaneCoverageState.PARTIAL
    return LaneCoverageState.COMPLETE


def _revision_changes(
    inputs: DiffusionInputs,
) -> tuple[tuple[DiffusionChange, ...], tuple[str, ...]]:
    grouped: dict[tuple[str, str, str], list[ScienceVersion]] = defaultdict(list)
    for version in inputs.versions:
        grouped[
            (version.key.kind.value, version.key.owner_id, version.key.local_id)
        ].append(version)
    changes: list[DiffusionChange] = []
    diagnostics: list[str] = []
    for group in grouped.values():
        ordered = sorted(group, key=lambda row: row.key.revision_index)
        for previous, current in pairwise(ordered):
            changed = compare_science_versions(previous, current)
            if not changed:
                continue
            changes.append(
                DiffusionChange(
                    change_key=(f"revision:{current.key.token()}:{'+'.join(changed)}"),
                    kind=DiffusionChangeKind.MUTATION,
                    from_version=previous.key,
                    to_version=current.key,
                    carrier_id=None,
                    confirmation_boundary=current.first_observed_boundary,
                    changed_fields=changed,
                )
            )
    return tuple(
        sorted(changes, key=lambda row: (row.confirmation_boundary, row.change_key))
    ), tuple(sorted(set(diagnostics)))


def _variant_changes(
    inputs: DiffusionInputs,
) -> tuple[DiffusionChange, ...]:
    changes: dict[str, DiffusionChange] = {}
    for occurrence in inputs.occurrences:
        source = occurrence.source_version
        variant = occurrence.variant_version
        if source is None or variant is None:
            continue
        left = inputs.version(source)
        right = inputs.version(variant)
        if left is None or right is None:
            continue
        changed = compare_science_versions(left, right)
        if not changed:
            continue
        key = f"variant:{occurrence.evidence.qualified_key()!r}:{'+'.join(changed)}"
        changes.setdefault(
            key,
            DiffusionChange(
                change_key=key,
                kind=DiffusionChangeKind.MUTATION,
                from_version=source,
                to_version=variant,
                carrier_id=occurrence.carrier_id,
                confirmation_boundary=occurrence.first_observed_boundary,
                changed_fields=changed,
            ),
        )
    return tuple(
        sorted(
            changes.values(),
            key=lambda row: (row.confirmation_boundary, row.change_key),
        )
    )


def _understanding_changes(
    inputs: DiffusionInputs,
) -> tuple[DiffusionChange, ...]:
    changes: dict[str, DiffusionChange] = {}
    for occurrence in inputs.occurrences:
        if occurrence.resolution is not DiffusionResolution.CONFIRMED:
            continue
        detail = dict(occurrence.detail)
        divergent = (
            detail.get("divergent_read") == "1" or detail.get("distorted") == "1"
        )
        adopted_divergence = False
        if (
            occurrence.stage is DiffusionStage.ADOPTED
            and occurrence.source_version is not None
            and occurrence.target_version is not None
        ):
            left = inputs.version(occurrence.source_version)
            right = inputs.version(occurrence.target_version)
            if left is not None and right is not None:
                adopted_divergence = bool(compare_science_versions(left, right))
        if not divergent and not adopted_divergence:
            continue
        key = f"misunderstanding:{_transmission_key(occurrence)}"
        changes.setdefault(
            key,
            DiffusionChange(
                change_key=key,
                kind=DiffusionChangeKind.MISUNDERSTANDING,
                from_version=occurrence.source_version,
                to_version=occurrence.target_version,
                carrier_id=occurrence.carrier_id,
                confirmation_boundary=occurrence.first_observed_boundary,
                changed_fields=(),
            ),
        )
    return tuple(
        sorted(
            changes.values(),
            key=lambda row: (row.confirmation_boundary, row.change_key),
        )
    )


def _translation_changes(
    inputs: DiffusionInputs,
) -> tuple[DiffusionChange, ...]:
    changes: list[DiffusionChange] = []
    for occurrence in inputs.occurrences:
        if "translation_applied" not in {
            flag.value for flag in occurrence.context_flags
        }:
            continue
        changes.append(
            DiffusionChange(
                change_key=f"translation:{_transmission_key(occurrence)}",
                kind=DiffusionChangeKind.TRANSLATION,
                from_version=occurrence.source_version,
                to_version=occurrence.target_version,
                carrier_id=occurrence.carrier_id,
                confirmation_boundary=occurrence.first_observed_boundary,
            )
        )
    return tuple(
        sorted(changes, key=lambda row: (row.confirmation_boundary, row.change_key))
    )


def _explicit_losses(
    inputs: DiffusionInputs,
) -> tuple[tuple[DiffusionLoss, ...], tuple[str, ...]]:
    losses: list[DiffusionLoss] = []
    diagnostics: list[str] = []
    for version in inputs.versions:
        wire = dict(version.wire)
        retired = wire.get("status") == "retired" or wire.get("lifecycle") == "retired"
        if not retired:
            continue
        losses.append(
            DiffusionLoss(
                loss_key=f"retire:{version.key.token()}",
                scope=DiffusionLossScope.OWNER_VERSION,
                version_key=version.key,
                carrier_id=None,
                witness_tick=version.occurrence_tick,
                witness_boundary=version.first_observed_boundary,
                confirmed=True,
                confirmation_boundary=version.first_observed_boundary,
            )
        )
    for occurrence in inputs.occurrences:
        detail = dict(occurrence.detail)
        if occurrence.occurrence_kind not in {
            "carrier_destroyed",
            "marker_removed",
        } and (
            detail.get("carrier_destroyed") != "1"
            and detail.get("marker_removed") != "1"
        ):
            continue
        losses.append(
            DiffusionLoss(
                loss_key=f"carrier:{occurrence.evidence.qualified_key()!r}",
                scope=DiffusionLossScope.PHYSICAL_CARRIER,
                version_key=occurrence.source_version,
                carrier_id=occurrence.carrier_id,
                witness_tick=occurrence.tick,
                witness_boundary=occurrence.first_observed_boundary,
                confirmed=True,
                confirmation_boundary=occurrence.first_observed_boundary,
            )
        )
    return tuple(
        sorted(losses, key=lambda row: (row.witness_boundary, row.loss_key))
    ), tuple(sorted(set(diagnostics)))


def _observed_lineage_losses(
    inputs: DiffusionInputs,
    windows: tuple[DiffusionWindow, ...],
    closures: tuple[CarrierClosureWitness, ...],
    explicit: tuple[DiffusionLoss, ...],
) -> tuple[tuple[DiffusionLoss, ...], tuple[str, ...]]:
    confirmed: list[DiffusionLoss] = []
    diagnostics: list[str] = []
    for witness in closures:
        if not witness.holders_closed or not witness.carriers_closed:
            diagnostics.append(DiffusionReason.COVERAGE_GAP.value)
            continue
        start = (
            (witness.witness_boundary + DIFFUSION_WINDOW_TICKS - 1)
            // DIFFUSION_WINDOW_TICKS
        ) * DIFFUSION_WINDOW_TICKS
        first = next((row for row in windows if row.start_tick == start), None)
        second = next(
            (
                row
                for row in windows
                if row.start_tick == start + DIFFUSION_WINDOW_TICKS
            ),
            None,
        )
        required = (
            DiffusionLane.SCIENCE,
            DiffusionLane.SPEECH,
            DiffusionLane.RECORDS,
        )
        if (
            first is None
            or second is None
            or not first.complete_for(required)
            or not second.complete_for(required)
        ):
            diagnostics.append(DiffusionReason.COVERAGE_GAP.value)
            continue
        related = [
            row
            for row in explicit
            if (witness.version_key is None or row.version_key == witness.version_key)
            and (not witness.carrier_key or row.carrier_id == witness.carrier_key)
        ]
        confirmed.append(
            DiffusionLoss(
                loss_key=f"observed:{witness.witness_boundary}:{witness.carrier_key}",
                scope=DiffusionLossScope.OBSERVED_LINEAGE,
                version_key=witness.version_key,
                carrier_id=witness.carrier_key or None,
                witness_tick=witness.witness_boundary,
                witness_boundary=witness.witness_boundary,
                confirmed=True,
                confirmation_boundary=second.end_tick_exclusive,
            )
        )
        _ = related
    return tuple(confirmed), tuple(sorted(set(diagnostics)))


def _complete_prior_coverage(inputs: DiffusionInputs, formation_tick: int) -> bool:
    required = (
        DiffusionLane.SCIENCE,
        DiffusionLane.SPEECH,
        DiffusionLane.TEACHING,
        DiffusionLane.RECORDS,
    )
    for lane in required:
        rows = [
            row
            for row in inputs.coverage
            if row.lane is lane
            and row.start_tick <= 0
            and row.end_tick_exclusive >= max(formation_tick, 1)
        ]
        if not rows or any(row.state is not LaneCoverageState.COMPLETE for row in rows):
            return False
    return True


def _rediscoveries(
    inputs: DiffusionInputs,
    losses: tuple[DiffusionLoss, ...],
    roots: tuple[RediscoveryRoot, ...],
) -> tuple[tuple[DiffusionRediscovery, ...], int, int, tuple[str, ...]]:
    confirmed = [row for row in losses if row.confirmed]
    rediscoveries: list[DiffusionRediscovery] = []
    origin_unresolved = 0
    convergence = 0
    diagnostics: list[str] = []
    root_by_version = {row.version_key: row for row in roots}
    for loss in confirmed:
        if loss.version_key is None:
            continue
        lost = inputs.version(loss.version_key)
        if lost is None:
            continue
        confirmation = loss.confirmation_boundary or loss.witness_boundary
        for candidate in inputs.versions:
            if candidate.key == lost.key or candidate.key.kind is not lost.key.kind:
                continue
            if candidate.occurrence_tick < confirmation:
                continue
            if compare_science_versions(lost, candidate):
                continue
            linked = [
                row
                for row in inputs.occurrences
                if row.target_version == candidate.key
                and row.resolution is DiffusionResolution.CONFIRMED
                and row.source_version is not None
            ]
            if linked:
                rediscoveries.append(
                    DiffusionRediscovery(
                        rediscovery_key=f"reacquired:{candidate.key.token()}",
                        kind=DiffusionRediscoveryKind.REACQUIRED,
                        version_key=candidate.key,
                        root_kind="linked_uptake",
                        root_ref=_transmission_key(linked[0]),
                        confirmation_boundary=candidate.first_observed_boundary,
                    )
                )
                continue
            root = root_by_version.get(candidate.key)
            if (
                root is not None
                and root.affirmative
                and root.committed
                and _complete_prior_coverage(inputs, candidate.occurrence_tick)
            ):
                rediscoveries.append(
                    DiffusionRediscovery(
                        rediscovery_key=f"independent:{candidate.key.token()}",
                        kind=DiffusionRediscoveryKind.INDEPENDENT,
                        version_key=candidate.key,
                        root_kind=root.root_kind,
                        root_ref=root.root_ref,
                        confirmation_boundary=candidate.first_observed_boundary,
                    )
                )
            elif root is not None:
                origin_unresolved += 1
            else:
                origin_unresolved += 1
    if not confirmed:
        for candidate in inputs.versions:
            root = root_by_version.get(candidate.key)
            if root is not None and root.affirmative and root.committed:
                convergence += 1
    return (
        tuple(
            sorted(
                rediscoveries,
                key=lambda row: (row.confirmation_boundary, row.rediscovery_key),
            )
        ),
        origin_unresolved,
        convergence,
        tuple(sorted(set(diagnostics))),
    )


def derive_science_diffusion(
    inputs: DiffusionInputs,
    *,
    v3_links: tuple[V3Link, ...] = (),
    closure_witnesses: tuple[CarrierClosureWitness, ...] = (),
    rediscovery_roots: tuple[RediscoveryRoot, ...] = (),
) -> DiffusionAssessment:
    """Fold one bounded input into a deterministic detached assessment."""

    if type(inputs) is not DiffusionInputs:
        raise DiffusionError(DiffusionReason.UNSUPPORTED_SCHEMA.value)
    windows = _windows(inputs)
    transmissions = _transmission_rows(inputs.occurrences)
    edges, edge_diagnostics = _edge_rows(inputs.occurrences)
    revision_changes, revision_diagnostics = _revision_changes(inputs)
    changes = (
        revision_changes
        + _variant_changes(inputs)
        + _understanding_changes(inputs)
        + _translation_changes(inputs)
    )
    explicit_losses, loss_diagnostics = _explicit_losses(inputs)
    observed_losses, observed_diagnostics = _observed_lineage_losses(
        inputs, windows, closure_witnesses, explicit_losses
    )
    losses = explicit_losses + observed_losses
    losses = tuple(sorted(losses, key=lambda row: (row.witness_boundary, row.loss_key)))
    rediscoveries, origin_unresolved, convergence, rediscovery_diagnostics = (
        _rediscoveries(inputs, losses, rediscovery_roots)
    )
    diagnostics = (
        edge_diagnostics
        + revision_diagnostics
        + loss_diagnostics
        + observed_diagnostics
        + rediscovery_diagnostics
    )
    _LOG.debug(
        "science_diffusion_assessed run_id=%s windows=%s transmissions=%s "
        "edges=%s changes=%s losses=%s rediscoveries=%s",
        inputs.run_id,
        len(windows),
        len(transmissions),
        len(edges),
        len(changes),
        len(losses),
        len(rediscoveries),
    )
    return DiffusionAssessment(
        run_id=inputs.run_id,
        windows=windows,
        transmissions=transmissions,
        edges=edges,
        changes=tuple(
            sorted(
                changes,
                key=lambda row: (row.confirmation_boundary, row.change_key),
            )
        ),
        losses=losses,
        rediscoveries=rediscoveries,
        v3_links=tuple(sorted(v3_links, key=lambda row: row.transmission_key)),
        diagnostics=tuple(sorted(set(diagnostics))),
        origin_unresolved=origin_unresolved,
        convergence_candidates=convergence,
    )
