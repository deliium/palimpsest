"""Trusted completed-run projection of objective scientific-practice receipts.

Only committed events and tick-matched detached inventories are read. The
projection keeps receipt identities, typed carrier references, and per-window
coverage; it never retains raw owner snapshots or full event payloads between
windows and never changes commands, results, or replay history.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.scientific_institutions_contract import (
    MAX_BOUNDARY_OWNERS,
    PRACTICE_WINDOW_TICKS,
    PracticeCarrierAction,
    PracticeCarrierFact,
    PracticeCarrierKind,
    PracticeCarrierSurvivalFact,
    PracticeCoverage,
    PracticeCoverageStatus,
    PracticeExecutionFact,
    PracticeLane,
    PracticeWindow,
    ScientificInstitutionsError,
    derive_practice_token,
    require_boundary_owner_cap,
    require_cumulative_event_cap,
    require_practice_window_index,
)
from simulation import (
    ObjectiveFacts,
    SimulationRunnerConfig,
    SimulationRunnerResult,
    hash_world_event,
    runner_config_fingerprint,
)
from simulation.fork_checkpoint import FinalizedResearchBoundary
from world.artifacts import (
    DURABLE_CAPABLE_ARTIFACT_KINDS,
    ArtifactKind,
    InformationArtifact,
    RecordIntegrity,
)
from world.events import (
    ArtifactAnnotated,
    ArtifactCopied,
    ArtifactCreated,
    ExperimentResolved,
    RepositoryMemberDeposited,
    RepositoryMemberRetrieved,
    WorldEvent,
)
from world.repositories import RepositoryStatus

__all__ = [
    "PracticeCarrierSurvivalFact",
    "ScientificInstitutionBoundaryInput",
    "ScientificInstitutionEvidence",
    "ScientificInstitutionWindowEvidence",
    "build_scientific_institution_windows",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_institutions_completed_run"
)

_DURABLE_ARTIFACT_KINDS: Final[frozenset[ArtifactKind]] = (
    DURABLE_CAPABLE_ARTIFACT_KINDS
)


@dataclass(frozen=True, slots=True)
class ScientificInstitutionBoundaryInput:
    """One finalized boundary export paired with its detached inventory."""

    boundary: FinalizedResearchBoundary
    inventory: ObjectiveFacts

    def __post_init__(self) -> None:
        if type(self.boundary) is not FinalizedResearchBoundary:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_boundary"
            )
        if type(self.inventory) is not ObjectiveFacts:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_inventory"
            )


@dataclass(frozen=True, slots=True)
class ScientificInstitutionWindowEvidence:
    """Objective receipts and surviving carriers for one fixed window."""

    window: PracticeWindow
    executions: tuple[PracticeExecutionFact, ...]
    carriers: tuple[PracticeCarrierFact, ...]
    surviving_carriers: tuple[PracticeCarrierSurvivalFact, ...]

    def __post_init__(self) -> None:
        if type(self.window) is not PracticeWindow:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_window"
            )
        object.__setattr__(
            self,
            "executions",
            tuple(
                sorted(
                    self.executions,
                    key=lambda row: (row.tick, row.occurrence_token),
                )
            ),
        )
        object.__setattr__(
            self,
            "carriers",
            tuple(
                sorted(
                    self.carriers,
                    key=lambda row: (row.tick, row.occurrence_token),
                )
            ),
        )
        object.__setattr__(
            self,
            "surviving_carriers",
            tuple(
                sorted(
                    self.surviving_carriers,
                    key=lambda row: (
                        row.carrier_kind.value,
                        row.carrier_token,
                        row.member_token or "",
                    ),
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class ScientificInstitutionEvidence:
    """Bounded detached evidence for one completed run."""

    run_id: str
    config_fingerprint: str
    windows: tuple[ScientificInstitutionWindowEvidence, ...]

    def __post_init__(self) -> None:
        indexes = tuple(item.window.window_index for item in self.windows)
        if indexes != tuple(range(len(indexes))):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_window"
            )

    def window(self, window_index: int) -> ScientificInstitutionWindowEvidence:
        for item in self.windows:
            if item.window.window_index == window_index:
                return item
        raise ScientificInstitutionsError("scientific_institutions_unknown_window")


def _event_hash(event: WorldEvent) -> str:
    try:
        return hash_world_event(event).value
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ScientificInstitutionsError(
            "scientific_institutions_event_hash_invalid"
        ) from exc


def _require_ordered_events(
    name: str, events: Sequence[WorldEvent]
) -> tuple[WorldEvent, ...]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise ScientificInstitutionsError("scientific_institutions_invalid_events")
    ordered: list[WorldEvent] = []
    previous: tuple[str, int, int] | None = None
    seen: set[str] = set()
    for event in events:
        if type(event) is not WorldEvent:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_events"
            )
        event_id = event.event_id.value
        if event_id in seen:
            raise ScientificInstitutionsError(
                "scientific_institutions_duplicate_event"
            )
        seen.add(event_id)
        key = (event.run_id, event.tick, event.sequence)
        if previous is not None and key < previous:
            raise ScientificInstitutionsError(
                f"scientific_institutions_invalid_{name}_order"
            )
        previous = key
        ordered.append(event)
    return tuple(ordered)


def _validate_result(
    result: SimulationRunnerResult, config: SimulationRunnerConfig
) -> tuple[str, str]:
    if type(result) is not SimulationRunnerResult:
        raise ScientificInstitutionsError("scientific_institutions_invalid_result")
    if type(config) is not SimulationRunnerConfig:
        raise ScientificInstitutionsError("scientific_institutions_invalid_config")
    run_id = result.run_id.value
    fingerprint = runner_config_fingerprint(config)
    receipts = result.finalized_tick_receipts
    if len(receipts) != result.ticks_committed:
        raise ScientificInstitutionsError(
            "scientific_institutions_receipt_mismatch"
        )
    for index, receipt in enumerate(receipts):
        if receipt.tick != index or receipt.resulting_tick != index + 1:
            raise ScientificInstitutionsError(
                "scientific_institutions_receipt_mismatch"
            )
    require_cumulative_event_cap(result.ticks_committed)
    return run_id, fingerprint


def _validate_boundaries(
    inputs: Sequence[ScientificInstitutionBoundaryInput],
    *,
    run_id: str,
    fingerprint: str,
    ticks_committed: int,
) -> tuple[ScientificInstitutionBoundaryInput, ...]:
    if isinstance(inputs, (str, bytes)) or not isinstance(inputs, Sequence):
        raise ScientificInstitutionsError("scientific_institutions_invalid_boundary")
    ordered = tuple(sorted(inputs, key=lambda item: item.boundary.boundary_tick.value))
    seen_ticks: set[int] = set()
    previous_tick = -1
    previous_revision = -1
    for item in ordered:
        if type(item) is not ScientificInstitutionBoundaryInput:
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_boundary"
            )
        boundary = item.boundary
        tick = boundary.boundary_tick.value
        revision = boundary.boundary_revision.value
        if boundary.run_id.value != run_id:
            raise ScientificInstitutionsError(
                "scientific_institutions_run_mismatch"
            )
        if boundary.config_fingerprint != fingerprint:
            raise ScientificInstitutionsError(
                "scientific_institutions_config_mismatch"
            )
        if tick in seen_ticks:
            raise ScientificInstitutionsError(
                "scientific_institutions_duplicate_boundary"
            )
        if tick < previous_tick:
            raise ScientificInstitutionsError(
                "scientific_institutions_decreasing_boundary"
            )
        if revision < previous_revision:
            raise ScientificInstitutionsError(
                "scientific_institutions_regressing_revision"
            )
        if tick > ticks_committed:
            raise ScientificInstitutionsError(
                "scientific_institutions_boundary_beyond_result"
            )
        if item.inventory.tick != tick or item.inventory.revision != revision:
            raise ScientificInstitutionsError(
                "scientific_institutions_inventory_mismatch"
            )
        if len(boundary.owners) > MAX_BOUNDARY_OWNERS:
            raise ScientificInstitutionsError(
                "scientific_institutions_owner_cap"
            )
        require_boundary_owner_cap(len(boundary.owners))
        require_cumulative_event_cap(len(boundary.events))
        seen_ticks.add(tick)
        previous_tick = tick
        previous_revision = revision
    return ordered


def _identity_maps(
    inputs: Sequence[ScientificInstitutionBoundaryInput],
) -> dict[str, str]:
    entity_to_agent: dict[str, str] = {}
    for item in inputs:
        for owner in item.boundary.owners:
            entity = owner.entity_id.value
            agent = owner.owner_id.value
            existing = entity_to_agent.get(entity)
            if existing is not None and existing != agent:
                raise ScientificInstitutionsError(
                    "scientific_institutions_ambiguous_identity"
                )
            entity_to_agent[entity] = agent
    return entity_to_agent


def _baseline_map(
    baseline_events: Sequence[WorldEvent],
) -> dict[str, str]:
    baseline = _require_ordered_events("baseline", baseline_events)
    require_cumulative_event_cap(len(baseline))
    mapping: dict[str, str] = {}
    for event in baseline:
        key = event.event_id.value
        digest = _event_hash(event)
        existing = mapping.get(key)
        if existing is not None and existing != digest:
            raise ScientificInstitutionsError(
                "scientific_institutions_event_hash_mismatch"
            )
        mapping[key] = digest
    return mapping


def _validate_prefixes(
    per_boundary: Sequence[tuple[str, tuple[WorldEvent, ...]]],
    baseline: Mapping[str, str],
) -> tuple[dict[str, WorldEvent], set[str]]:
    known: dict[str, WorldEvent] = {}
    known_hashes: dict[str, str] = {}
    previous_ids: tuple[str, ...] = ()
    excluded: set[str] = set()
    for _, events in per_boundary:
        ids: list[str] = []
        for event in events:
            event_id = event.event_id.value
            digest = _event_hash(event)
            if event_id in known_hashes:
                if known_hashes[event_id] != digest:
                    raise ScientificInstitutionsError(
                        "scientific_institutions_event_hash_mismatch"
                    )
            else:
                known_hashes[event_id] = digest
                known[event_id] = event
            ids.append(event_id)
            if event_id in baseline:
                if baseline[event_id] != digest:
                    raise ScientificInstitutionsError(
                        "scientific_institutions_event_hash_mismatch"
                    )
                excluded.add(event_id)
        current = tuple(ids)
        if current[: len(previous_ids)] != previous_ids:
            raise ScientificInstitutionsError(
                "scientific_institutions_event_prefix_mismatch"
            )
        previous_ids = current
    return known, excluded


def _artifact_kind_map(
    known: Mapping[str, WorldEvent],
    inputs: Sequence[ScientificInstitutionBoundaryInput],
) -> dict[str, ArtifactKind]:
    kinds: dict[str, ArtifactKind] = {}
    for event in known.values():
        if isinstance(event.details, ArtifactCreated):
            kinds.setdefault(
                event.details.artifact_id.value, event.details.artifact_kind
            )
    for item in inputs:
        for artifact in item.inventory.artifacts:
            existing = kinds.get(artifact.artifact_id.value)
            if existing is not None and existing is not artifact.kind:
                raise ScientificInstitutionsError(
                    "scientific_institutions_conflicting_carrier"
                )
            kinds[artifact.artifact_id.value] = artifact.kind
    return kinds


def _durable_artifact_kind(
    artifact_id: str,
    *,
    kinds: Mapping[str, ArtifactKind],
    config: SimulationRunnerConfig,
) -> ArtifactKind | None:
    if config.durable_records is None:
        return None
    kind = kinds.get(artifact_id)
    if kind is None or kind not in _DURABLE_ARTIFACT_KINDS:
        return None
    return kind


def _carrier_kind(kind: ArtifactKind) -> PracticeCarrierKind:
    if kind is ArtifactKind.RECORD:
        return PracticeCarrierKind.RECORD
    return PracticeCarrierKind.ARTIFACT


def _actor_token(
    event: WorldEvent,
    *,
    run_id: str,
    entity_to_agent: Mapping[str, str],
) -> str:
    actor = event.actor_id
    if actor is None:
        raise ScientificInstitutionsError(
            "scientific_institutions_unmapped_actor"
        )
    agent = entity_to_agent.get(actor.value)
    if agent is None:
        raise ScientificInstitutionsError(
            "scientific_institutions_unmapped_actor"
        )
    return derive_practice_token("actor", run_id, agent)


def _occurrence_token(event: WorldEvent, run_id: str) -> str:
    return derive_practice_token("occurrence", run_id, event.event_id.value)


def _carrier_token(entity_id: str, run_id: str) -> str:
    return derive_practice_token("carrier", run_id, entity_id)


def _source_root_token(entity_id: str, run_id: str) -> str:
    return derive_practice_token("source_root", run_id, entity_id)


def _window_slice(
    events: Sequence[WorldEvent],
    *,
    start_tick: int,
    end_tick: int,
) -> tuple[WorldEvent, ...]:
    return tuple(
        event for event in events if start_tick <= event.tick < end_tick
    )


def _event_counts(
    events: Iterable[WorldEvent], *, start_tick: int, end_tick: int
) -> dict[int, int]:
    counts = {tick: 0 for tick in range(start_tick, end_tick)}
    for event in events:
        if event.tick in counts:
            counts[event.tick] += 1
    return counts


def _validate_event_counts(
    result: SimulationRunnerResult,
    *,
    boundary: FinalizedResearchBoundary,
    start_tick: int,
    end_tick: int,
) -> None:
    raw = _window_slice(boundary.events, start_tick=start_tick, end_tick=end_tick)
    counts = _event_counts(raw, start_tick=start_tick, end_tick=end_tick)
    for tick, observed in counts.items():
        receipt = result.finalized_tick_receipts[tick]
        if receipt.event_count != observed:
            raise ScientificInstitutionsError(
                "scientific_institutions_event_count_mismatch"
            )


def _execution_facts(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    entity_to_agent: Mapping[str, str],
) -> list[PracticeExecutionFact]:
    facts: list[PracticeExecutionFact] = []
    for event in events:
        details = event.details
        if not isinstance(details, ExperimentResolved):
            continue
        if details.discovery_mode != "deliberate":
            continue
        facts.append(
            PracticeExecutionFact(
                run_id=run_id,
                occurrence_token=_occurrence_token(event, run_id),
                actor_token=_actor_token(
                    event, run_id=run_id, entity_to_agent=entity_to_agent
                ),
                tick=event.tick,
                operator=details.operator,
                process_token=details.process_token,
            )
        )
    return facts


def _carrier_facts(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    entity_to_agent: Mapping[str, str],
    artifact_kinds: Mapping[str, ArtifactKind],
    config: SimulationRunnerConfig,
    inventory: ObjectiveFacts,
) -> tuple[list[PracticeCarrierFact], list[PracticeCarrierSurvivalFact]]:
    facts: list[PracticeCarrierFact] = []
    roots: dict[str, str] = {
        artifact.artifact_id.value: (
            artifact.source_artifact_id or artifact.artifact_id
        ).value
        for artifact in inventory.artifacts
    }
    repository_ids = {row.repository_id.value for row in inventory.repositories}
    for event in events:
        details = event.details
        if not isinstance(
            details,
            (
                ArtifactCreated,
                ArtifactAnnotated,
                ArtifactCopied,
                RepositoryMemberDeposited,
                RepositoryMemberRetrieved,
            ),
        ):
            continue
        actor = _actor_token(
            event, run_id=run_id, entity_to_agent=entity_to_agent
        )
        occurrence = _occurrence_token(event, run_id)
        if isinstance(details, ArtifactCreated):
            artifact_id = details.artifact_id.value
            if (
                _durable_artifact_kind(
                    artifact_id, kinds=artifact_kinds, config=config
                )
                is None
            ):
                continue
            roots.setdefault(artifact_id, artifact_id)
            facts.append(
                PracticeCarrierFact(
                    run_id=run_id,
                    occurrence_token=occurrence,
                    actor_token=actor,
                    tick=event.tick,
                    carrier_kind=_carrier_kind(details.artifact_kind),
                    carrier_token=_carrier_token(artifact_id, run_id),
                    source_root_token=_source_root_token(
                        roots.get(artifact_id, artifact_id), run_id
                    ),
                    action=PracticeCarrierAction.CREATE,
                )
            )
        elif isinstance(details, ArtifactAnnotated):
            artifact_id = details.artifact_id.value
            kind = _durable_artifact_kind(
                artifact_id, kinds=artifact_kinds, config=config
            )
            if kind is None:
                continue
            facts.append(
                PracticeCarrierFact(
                    run_id=run_id,
                    occurrence_token=occurrence,
                    actor_token=actor,
                    tick=event.tick,
                    carrier_kind=_carrier_kind(kind),
                    carrier_token=_carrier_token(artifact_id, run_id),
                    source_root_token=_source_root_token(
                        roots.get(artifact_id, artifact_id), run_id
                    ),
                    action=PracticeCarrierAction.ANNOTATE,
                )
            )
        elif isinstance(details, ArtifactCopied):
            child = details.child_artifact_id.value
            parent = details.parent_artifact_id.value
            if (
                _durable_artifact_kind(child, kinds=artifact_kinds, config=config)
                is None
            ):
                continue
            root = roots.get(parent, parent)
            roots[child] = root
            facts.append(
                PracticeCarrierFact(
                    run_id=run_id,
                    occurrence_token=occurrence,
                    actor_token=actor,
                    tick=event.tick,
                    carrier_kind=_carrier_kind(
                        artifact_kinds.get(child, ArtifactKind.RECORD)
                    ),
                    carrier_token=_carrier_token(child, run_id),
                    source_root_token=_source_root_token(root, run_id),
                    action=PracticeCarrierAction.COPY,
                    parent_token=_carrier_token(parent, run_id),
                )
            )
        elif isinstance(
            details, (RepositoryMemberDeposited, RepositoryMemberRetrieved)
        ):
            repository_id = details.repository_id.value
            artifact_id = details.artifact_id.value
            if repository_id not in repository_ids:
                continue
            if config.knowledge_repositories is None:
                continue
            if (
                _durable_artifact_kind(
                    artifact_id, kinds=artifact_kinds, config=config
                )
                is None
            ):
                continue
            action = (
                PracticeCarrierAction.DEPOSIT
                if isinstance(details, RepositoryMemberDeposited)
                else PracticeCarrierAction.RETRIEVE
            )
            facts.append(
                PracticeCarrierFact(
                    run_id=run_id,
                    occurrence_token=occurrence,
                    actor_token=actor,
                    tick=event.tick,
                    carrier_kind=PracticeCarrierKind.REPOSITORY_MEMBER,
                    carrier_token=_carrier_token(repository_id, run_id),
                    source_root_token=_source_root_token(
                        roots.get(artifact_id, artifact_id), run_id
                    ),
                    action=action,
                    member_token=_carrier_token(artifact_id, run_id),
                )
            )
    surviving = _surviving_carriers(
        inventory=inventory,
        run_id=run_id,
        artifact_kinds=artifact_kinds,
        config=config,
    )
    return facts, surviving


def _surviving_carriers(
    *,
    inventory: ObjectiveFacts,
    run_id: str,
    artifact_kinds: Mapping[str, ArtifactKind],
    config: SimulationRunnerConfig,
) -> list[PracticeCarrierSurvivalFact]:
    surviving: list[PracticeCarrierSurvivalFact] = []
    live_artifacts: dict[str, InformationArtifact] = {}
    for artifact in inventory.artifacts:
        artifact_id = artifact.artifact_id.value
        if _durable_artifact_kind(
            artifact_id, kinds=artifact_kinds, config=config
        ) is None:
            continue
        if artifact.integrity is RecordIntegrity.DESTROYED:
            continue
        live_artifacts[artifact_id] = artifact
        root = (
            artifact.source_artifact_id or artifact.artifact_id
        ).value
        surviving.append(
            PracticeCarrierSurvivalFact(
                carrier_kind=_carrier_kind(artifact.kind),
                carrier_token=_carrier_token(artifact_id, run_id),
                source_root_token=_source_root_token(root, run_id),
            )
        )
    for repository in inventory.repositories:
        if repository.status is RepositoryStatus.DESTROYED:
            continue
        repository_id = repository.repository_id.value
        surviving.append(
            PracticeCarrierSurvivalFact(
                carrier_kind=PracticeCarrierKind.REPOSITORY,
                carrier_token=_carrier_token(repository_id, run_id),
                source_root_token=_source_root_token(repository_id, run_id),
            )
        )
        for member in repository.member_artifact_ids:
            member_id = member.value
            member_artifact = live_artifacts.get(member_id)
            if member_artifact is None:
                continue
            root = (
                member_artifact.source_artifact_id
                or member_artifact.artifact_id
            ).value
            surviving.append(
                PracticeCarrierSurvivalFact(
                    carrier_kind=PracticeCarrierKind.REPOSITORY_MEMBER,
                    carrier_token=_carrier_token(repository_id, run_id),
                    source_root_token=_source_root_token(root, run_id),
                    member_token=_carrier_token(member_id, run_id),
                )
            )
    return surviving


def _build_window(
    *,
    run_id: str,
    window_index: int,
    start_tick: int,
    end_tick: int,
    complete: bool,
    endpoint: ScientificInstitutionBoundaryInput | None,
    start_endpoint_present: bool,
    excluded: set[str],
    entity_to_agent: Mapping[str, str],
    artifact_kinds: Mapping[str, ArtifactKind],
    config: SimulationRunnerConfig,
) -> ScientificInstitutionWindowEvidence:
    if endpoint is None or not start_endpoint_present:
        status = PracticeCoverageStatus.UNAVAILABLE
        coverage = (
            PracticeCoverage(
                run_id=run_id,
                window_index=window_index,
                lane=PracticeLane.EXECUTION,
                status=status,
            ),
            PracticeCoverage(
                run_id=run_id,
                window_index=window_index,
                lane=PracticeLane.CARRIER,
                status=status,
            ),
        )
        return ScientificInstitutionWindowEvidence(
            window=PracticeWindow(
                run_id=run_id,
                window_index=window_index,
                start_tick=start_tick,
                end_tick_exclusive=end_tick,
                complete=complete,
                coverage=coverage,
            ),
            executions=(),
            carriers=(),
            surviving_carriers=(),
        )
    slice_events = tuple(
        event
        for event in _window_slice(
            endpoint.boundary.events, start_tick=start_tick, end_tick=end_tick
        )
        if event.event_id.value not in excluded
    )
    executions = _execution_facts(
        slice_events, run_id=run_id, entity_to_agent=entity_to_agent
    )
    carriers, surviving = _carrier_facts(
        slice_events,
        run_id=run_id,
        entity_to_agent=entity_to_agent,
        artifact_kinds=artifact_kinds,
        config=config,
        inventory=endpoint.inventory,
    )
    status = (
        PracticeCoverageStatus.COMPLETE
        if complete
        else PracticeCoverageStatus.PARTIAL
    )
    coverage = (
        PracticeCoverage(
            run_id=run_id,
            window_index=window_index,
            lane=PracticeLane.EXECUTION,
            status=status,
        ),
        PracticeCoverage(
            run_id=run_id,
            window_index=window_index,
            lane=PracticeLane.CARRIER,
            status=status,
        ),
    )
    return ScientificInstitutionWindowEvidence(
        window=PracticeWindow(
            run_id=run_id,
            window_index=window_index,
            start_tick=start_tick,
            end_tick_exclusive=end_tick,
            complete=complete,
            coverage=coverage,
        ),
        executions=tuple(executions),
        carriers=tuple(carriers),
        surviving_carriers=tuple(surviving),
    )


def build_scientific_institution_windows(
    result: SimulationRunnerResult,
    config: SimulationRunnerConfig,
    inputs: Sequence[ScientificInstitutionBoundaryInput],
    *,
    baseline_events: Sequence[WorldEvent] = (),
) -> ScientificInstitutionEvidence:
    """Project admitted science and carrier receipts into fixed windows."""

    run_id, fingerprint = _validate_result(result, config)
    boundaries = _validate_boundaries(
        inputs,
        run_id=run_id,
        fingerprint=fingerprint,
        ticks_committed=result.ticks_committed,
    )
    entity_to_agent = _identity_maps(boundaries)
    baseline = _baseline_map(baseline_events)
    per_boundary: list[tuple[str, tuple[WorldEvent, ...]]] = []
    for item in boundaries:
        events = _require_ordered_events("boundary", item.boundary.events)
        for event in events:
            if event.tick >= item.boundary.boundary_tick.value:
                raise ScientificInstitutionsError(
                    "scientific_institutions_invalid_boundary"
                )
        per_boundary.append(
            (str(item.boundary.boundary_tick.value), events)
        )
    known, excluded = _validate_prefixes(per_boundary, baseline)
    artifact_kinds = _artifact_kind_map(known, boundaries)
    by_tick = {
        item.boundary.boundary_tick.value: item for item in boundaries
    }
    if result.ticks_committed > 0:
        for item in boundaries:
            tick = item.boundary.boundary_tick.value
            if tick == 0:
                continue
            receipt = result.finalized_tick_receipts[tick - 1]
            if receipt.resulting_revision != item.boundary.boundary_revision.value:
                raise ScientificInstitutionsError(
                    "scientific_institutions_revision_mismatch"
                )
    total_windows = (
        result.ticks_committed + PRACTICE_WINDOW_TICKS - 1
    ) // PRACTICE_WINDOW_TICKS
    require_practice_window_index(max(0, total_windows - 1))
    windows: list[ScientificInstitutionWindowEvidence] = []
    for index in range(total_windows):
        start = index * PRACTICE_WINDOW_TICKS
        expected_end = min(
            start + PRACTICE_WINDOW_TICKS, result.ticks_committed
        )
        complete = (
            expected_end - start == PRACTICE_WINDOW_TICKS
        )
        endpoint = by_tick.get(expected_end)
        start_present = index == 0 or start in by_tick
        if endpoint is not None:
            _validate_event_counts(
                result,
                boundary=endpoint.boundary,
                start_tick=start,
                end_tick=expected_end,
            )
        windows.append(
            _build_window(
                run_id=run_id,
                window_index=index,
                start_tick=start,
                end_tick=expected_end,
                complete=complete,
                endpoint=endpoint,
                start_endpoint_present=start_present,
                excluded=excluded,
                entity_to_agent=entity_to_agent,
                artifact_kinds=artifact_kinds,
                config=config,
            )
        )
    _LOG.debug(
        "scientific_institutions_windows run_id=%s windows=%s complete=%s "
        "executions=%s carriers=%s boundaries=%s",
        run_id,
        len(windows),
        sum(1 for item in windows if item.window.complete),
        sum(len(item.executions) for item in windows),
        sum(len(item.carriers) for item in windows),
        len(boundaries),
    )
    return ScientificInstitutionEvidence(
        run_id=run_id,
        config_fingerprint=fingerprint,
        windows=tuple(windows),
    )
