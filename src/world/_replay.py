"""Pure objective-event projector for authoritative replay.

Applies recorded effect facts onto immutable ``WorldState`` without invoking
current command validation or behavioral rules. Production folds log on
``simulation.replay`` with counts and catalog digests only.

Compatibility:
- Replay schema v2: legacy take/drop/give mutations only.
- Replay schema v3/v4/v5: effect-complete physical projector for all mutating kinds.
  Schema v4/v5 additionally carry occurrence context (ignored by state projection).
  Schema v5 carries structured communication payloads (still projection no-ops).
- Replay schema v6: the same physical fold plus production events. A non-empty
  catalog supplies item and structure kinds the events do not repeat.
- Replay schema v7: the v6 fold plus season, band, node, and hazard witnesses.
  Hazards are stored as start tick and duration. Remaining ticks are derived.
- Replay schema v8: the v7 fold plus artifact create/modify/move/destroy.
  Mark tokens live on codec-v5 checkpoints; event folds carry identity,
  placement, and content revision only.
Runs never mix replay schema versions.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from world._state import WorldState, rebuild_world_state
from world.artifacts import ArtifactContent, InformationArtifact
from world.environment import (
    ActiveHazard,
    EnvironmentalDynamicsSpec,
    temperature_band,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V2,
    EVENT_SCHEMA_REPLAY_V3,
    EVENT_SCHEMA_REPLAY_V4,
    EVENT_SCHEMA_REPLAY_V5,
    EVENT_SCHEMA_REPLAY_V6,
    EVENT_SCHEMA_REPLAY_V7,
    EVENT_SCHEMA_REPLAY_V8,
    EVENT_SCHEMA_REPLAY_V9,
    EVENT_SCHEMA_REPLAY_V10,
    EVENT_SCHEMA_REPLAY_V11,
    EVENT_SCHEMA_REPLAY_V12,
    EVENT_SCHEMA_REPLAY_V13,
    EVENT_SCHEMA_REPLAY_V14,
    AgentCreated,
    AgentEnteredWorld,
    AgentInitializationRecorded,
    ArtifactAnnotated,
    ArtifactCopied,
    ArtifactCreated,
    ArtifactDamaged,
    ArtifactDestroyed,
    ArtifactModified,
    ArtifactMoved,
    ArtifactPartiallyLost,
    Asked,
    Attacked,
    CraftStarted,
    Died,
    Dropped,
    Drunk,
    Eaten,
    EnvironmentalHazardEnded,
    EnvironmentalHazardStarted,
    ExposureApplied,
    Fled,
    Fed,
    Given,
    Helped,
    ItemCrafted,
    ItemStored,
    KinshipEdgeRecorded,
    LifecycleStageChanged,
    Moved,
    RepositoryEstablished,
    RepositoryIndexed,
    RepositoryMaintained,
    RepositoryMemberDeposited,
    RepositoryMemberRetrieved,
    RepositoryNeglected,
    NeedsApplied,
    ResourceHarvested,
    ResourceNodeDepleted,
    ResourceNodeRecovered,
    ResourceRegenerated,
    Searched,
    SeasonChanged,
    Slept,
    StructureBuilt,
    StructureRepaired,
    Taken,
    Talked,
    TemperatureBandChanged,
    Told,
    Transported,
    Waited,
    WeatherChanged,
    WorldEvent,
    event_is_replayable,
    normalize_events,
    require_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    WorldId,
    WorldRevision,
    require_stable_id,
)
from world.lifecycle import default_entrant_body
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    PhysicalRules,
    copy_body,
    copy_item,
    copy_resource,
    copy_weather,
    default_physical_rules,
)
from world.production import (
    ItemProduct,
    ProductionCatalog,
    ProductionJob,
    Structure,
    StructureKind,
    ToolMark,
    production_catalog_digest,
)
from world.values import (
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    round_physical,
)

_LOG: Final[logging.Logger] = logging.getLogger("simulation.replay")

__all__: list[str] = [
    "ProjectionError",
    "ProjectionErrorCode",
    "project_event_prefix",
    "project_events",
]

_ITEM_KIND_FOR_RESOURCE: Final[dict[ResourceKind, ItemKind]] = {
    ResourceKind.FOOD: ItemKind.FOOD,
    ResourceKind.WATER: ItemKind.WATER,
    ResourceKind.MATERIAL: ItemKind.MATERIAL,
}


class ProjectionErrorCode(StrEnum):
    """Stable corruption/mismatch codes for restore orchestration logs."""

    NON_REPLAYABLE = "non_replayable_event"
    RUN_ID_MISMATCH = "run_id_mismatch"
    WORLD_ID_MISMATCH = "world_id_mismatch"
    DUPLICATE_EVENT = "duplicate_event_id"
    INVALID_ORDERING = "invalid_event_ordering"
    REVISION_MISMATCH = "revision_mismatch"
    ACTOR_MISSING = "actor_missing"
    TARGET_MISSING = "target_missing"
    PRECONDITION_FAILED = "precondition_failed"
    INVARIANT_FAILED = "invariant_failed"
    INVALID_SEQUENCE = "invalid_sequence"
    MIXED_SCHEMA = "mixed_replay_schema_version"
    UNSUPPORTED_SCHEMA = "unsupported_event_schema_version"
    CATALOG_MISMATCH = "production_catalog_mismatch"
    ENVIRONMENT_WITNESS_MISMATCH = "environment_witness_mismatch"


class ProjectionError(ValueError):
    """Fail-closed projection failure with a stable code and no payloads."""

    def __init__(self, code: ProjectionErrorCode | str) -> None:
        self.code = code.value if isinstance(code, ProjectionErrorCode) else code
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class _TickGroup:
    tick: int
    events: tuple[WorldEvent, ...]


def project_events(
    state: WorldState,
    events: Sequence[WorldEvent],
    *,
    expected_run_id: str,
    expected_world_id: WorldId,
    production_catalog: ProductionCatalog | None = None,
    environmental_dynamics: object | None = None,
) -> WorldState:
    """Fold ordered replay-capable events onto ``state``.

    Enforces run/world identity, contiguous per-tick sequences, revision
    transitions (0 or +1 per tick), duplicate rejection, and graph invariants.
    Does not call ``evaluate_operation`` / ``apply_operation``.
    """
    normalized, schema_version, run_id = _prepare_events(
        state,
        events,
        expected_run_id=expected_run_id,
        expected_world_id=expected_world_id,
    )
    if not normalized:
        return state

    working = state
    base_revision = state.revision
    seen_ids: set[EventId] = set()
    previous_tick: int | None = None

    for group in _group_by_tick(normalized):
        if previous_tick is not None and group.tick <= previous_tick:
            raise ProjectionError(ProjectionErrorCode.INVALID_ORDERING)
        previous_tick = group.tick
        working, base_revision = _project_tick_group(
            working,
            group,
            expected_run_id=run_id,
            expected_world_id=expected_world_id,
            base_revision=base_revision,
            seen_ids=seen_ids,
            schema_version=schema_version,
            assign_revision=True,
            production_catalog=production_catalog,
            environmental_dynamics=environmental_dynamics,
        )
        if schema_version == EVENT_SCHEMA_REPLAY_V6:
            _LOG.debug(
                "production_fold tick=%s structure_count=%s job_count=%s",
                group.tick,
                len(working.structures),
                len(working.production_jobs),
            )
        if schema_version == EVENT_SCHEMA_REPLAY_V8:
            _LOG.debug(
                "artifact_fold tick=%s artifact_count=%s",
                group.tick,
                len(working.artifacts),
            )
    return working


def project_event_prefix(
    state: WorldState,
    events: Sequence[WorldEvent],
    *,
    expected_run_id: str,
    expected_world_id: WorldId,
    includes_last_event: bool,
    production_catalog: ProductionCatalog | None = None,
    environmental_dynamics: object | None = None,
) -> WorldState:
    """Fold one tick prefix without treating a partial tick as complete.

    Applies effects in sequence order. The tick's resulting revision is
    assigned only when ``includes_last_event`` is true. A shorter prefix
    keeps the start-of-tick revision even when a later event in that tick
    records a higher revision.
    """
    if type(includes_last_event) is not bool:
        raise TypeError("includes_last_event must be bool")
    normalized, schema_version, run_id = _prepare_events(
        state,
        events,
        expected_run_id=expected_run_id,
        expected_world_id=expected_world_id,
    )
    if not normalized:
        raise ProjectionError(ProjectionErrorCode.INVALID_SEQUENCE)
    groups = _group_by_tick(normalized)
    if len(groups) != 1:
        raise ProjectionError(ProjectionErrorCode.INVALID_ORDERING)
    projected, _revision = _project_tick_group(
        state,
        groups[0],
        expected_run_id=run_id,
        expected_world_id=expected_world_id,
        base_revision=state.revision,
        seen_ids=set(),
            schema_version=schema_version,
            assign_revision=includes_last_event,
            production_catalog=production_catalog,
            environmental_dynamics=environmental_dynamics,
        )
    return projected


def _prepare_events(
    state: WorldState,
    events: Sequence[WorldEvent],
    *,
    expected_run_id: str,
    expected_world_id: WorldId,
) -> tuple[tuple[WorldEvent, ...], int, str]:
    if type(state) is not WorldState:
        raise TypeError("project_events requires WorldState")
    if type(expected_world_id) is not WorldId:
        raise TypeError("expected_world_id must be WorldId")
    run_id = require_stable_id("expected_run_id", expected_run_id)
    if isinstance(events, (set, frozenset, Mapping)):
        raise ProjectionError(ProjectionErrorCode.INVALID_SEQUENCE)
    if isinstance(events, (str, bytes, bytearray)) or not isinstance(events, Sequence):
        raise ProjectionError(ProjectionErrorCode.INVALID_SEQUENCE)

    try:
        normalized = normalize_events(events)
    except (TypeError, ValueError) as exc:
        message = str(exc)
        if "duplicate" in message:
            raise ProjectionError(ProjectionErrorCode.DUPLICATE_EVENT) from exc
        raise ProjectionError(ProjectionErrorCode.INVALID_SEQUENCE) from exc

    if not normalized:
        return normalized, state.revision.value, run_id

    schema_version = normalized[0].schema_version
    for event in normalized:
        if event.schema_version != schema_version:
            raise ProjectionError(ProjectionErrorCode.MIXED_SCHEMA)
        if event.schema_version not in {
            EVENT_SCHEMA_REPLAY_V2,
            EVENT_SCHEMA_REPLAY_V3,
            EVENT_SCHEMA_REPLAY_V4,
            EVENT_SCHEMA_REPLAY_V5,
            EVENT_SCHEMA_REPLAY_V6,
            EVENT_SCHEMA_REPLAY_V7,
            EVENT_SCHEMA_REPLAY_V8,
            EVENT_SCHEMA_REPLAY_V9,
            EVENT_SCHEMA_REPLAY_V10,
            EVENT_SCHEMA_REPLAY_V11,
            EVENT_SCHEMA_REPLAY_V12,
            EVENT_SCHEMA_REPLAY_V13,
            EVENT_SCHEMA_REPLAY_V14,
        }:
            raise ProjectionError(ProjectionErrorCode.UNSUPPORTED_SCHEMA)
    return normalized, schema_version, run_id


def _group_by_tick(events: tuple[WorldEvent, ...]) -> tuple[_TickGroup, ...]:
    groups: list[_TickGroup] = []
    index = 0
    while index < len(events):
        tick = events[index].tick
        start = index
        while index < len(events) and events[index].tick == tick:
            index += 1
        batch = events[start:index]
        for sequence, event in enumerate(batch):
            if event.sequence != sequence:
                raise ProjectionError(ProjectionErrorCode.INVALID_ORDERING)
        groups.append(_TickGroup(tick=tick, events=batch))
    return tuple(groups)


def _project_tick_group(
    state: WorldState,
    group: _TickGroup,
    *,
    expected_run_id: str,
    expected_world_id: WorldId,
    base_revision: WorldRevision,
    seen_ids: set[EventId],
    schema_version: int,
    assign_revision: bool,
    production_catalog: ProductionCatalog | None = None,
    environmental_dynamics: object | None = None,
) -> tuple[WorldState, WorldRevision]:
    resulting_revision = group.events[0].resulting_revision
    for event in group.events:
        _validate_event_identity(
            event,
            expected_run_id=expected_run_id,
            expected_world_id=expected_world_id,
            seen_ids=seen_ids,
        )
        if event.resulting_revision != resulting_revision:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
        if event.tick != group.tick:
            raise ProjectionError(ProjectionErrorCode.INVALID_ORDERING)

    working = state
    mutated = False
    for event in group.events:
        next_state, changed = _apply_event_effect(
            working,
            event,
            schema_version=schema_version,
            production_catalog=production_catalog,
            environmental_dynamics=environmental_dynamics,
        )
        working = next_state
        mutated = mutated or changed

    if not assign_revision:
        if working.revision != base_revision:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
        return working, base_revision

    if mutated:
        expected = WorldRevision(base_revision.value + 1)
        if resulting_revision != expected:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
        working = rebuild_world_state(working, revision=resulting_revision)
    else:
        if resulting_revision != base_revision:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
        if working.revision != base_revision:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)

    if working.revision != resulting_revision:
        raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
    if schema_version in {EVENT_SCHEMA_REPLAY_V7, EVENT_SCHEMA_REPLAY_V8}:
        season = (
            environmental_dynamics.season_at(group.tick).value
            if type(environmental_dynamics) is EnvironmentalDynamicsSpec
            else "-"
        )
        _LOG.debug(
            "environment_fold tick=%s season=%s hazard_count=%s resource_count=%s",
            group.tick,
            season,
            len(working.active_hazards),
            len(working.resources),
        )
    return working, resulting_revision


def _validate_event_identity(
    event: WorldEvent,
    *,
    expected_run_id: str,
    expected_world_id: WorldId,
    seen_ids: set[EventId],
) -> None:
    try:
        require_replayable_event(event)
    except (TypeError, ValueError) as exc:
        raise ProjectionError(ProjectionErrorCode.NON_REPLAYABLE) from exc
    if not event_is_replayable(event):
        raise ProjectionError(ProjectionErrorCode.NON_REPLAYABLE)
    if event.run_id != expected_run_id:
        raise ProjectionError(ProjectionErrorCode.RUN_ID_MISMATCH)
    if event.world_id != expected_world_id:
        raise ProjectionError(ProjectionErrorCode.WORLD_ID_MISMATCH)
    if event.event_id in seen_ids:
        raise ProjectionError(ProjectionErrorCode.DUPLICATE_EVENT)
    seen_ids.add(event.event_id)


def _validate_event_only_refs(state: WorldState, event: WorldEvent) -> None:
    if event.actor_id is not None and event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if event.target_id is not None and not _entity_known(state, event.target_id):
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)


def _entity_known(state: WorldState, entity_id: EntityId) -> bool:
    return (
        entity_id in state.bodies
        or entity_id in state.items
        or entity_id in state.locations
        or entity_id in state.resources
        or entity_id in state.structures
        or entity_id in state.artifacts
    )


def _apply_event_effect(
    state: WorldState,
    event: WorldEvent,
    *,
    schema_version: int,
    production_catalog: ProductionCatalog | None = None,
    environmental_dynamics: object | None = None,
) -> tuple[WorldState, bool]:
    if schema_version == EVENT_SCHEMA_REPLAY_V2:
        match event.details:
            case Taken() | Dropped() | Given():
                return _apply_legacy_transfer(state, event), True
            case _:
                _validate_event_only_refs(state, event)
                return state, False

    match event.details:
        case Searched(success=False) | Attacked(hit=False) | Fled(success=False):
            _validate_event_only_refs(state, event)
            return state, False
        case Talked() | Asked() | Told() | Waited():
            _validate_event_only_refs(state, event)
            return state, False
        case Taken() | Dropped() | Given():
            return _apply_legacy_transfer(state, event), True
        case Moved() as moved:
            return _project_move(state, event, moved), True
        case Searched() as searched if searched.success is True:
            return _project_search_success(state, event, searched), True
        case Eaten() as eaten:
            return _project_eat(state, event, eaten), True
        case Drunk() as drunk:
            return _project_drink(state, event, drunk), True
        case Slept() as slept:
            return _project_sleep(state, event, slept), True
        case Helped() as helped:
            return _project_help(state, event, helped), True
        case Fed() as fed:
            return _project_feed(state, event, fed), True
        case Transported() as transported:
            return _project_transport(state, event, transported), True
        case Attacked() as attacked if attacked.hit is True:
            return _project_attack_hit(state, event, attacked), True
        case Fled() as fled if fled.success is True:
            return _project_flee_success(state, event, fled), True
        case WeatherChanged() as weather:
            return _project_weather(state, weather), True
        case ResourceRegenerated() as regenerated:
            return _project_regeneration(state, regenerated), True
        case NeedsApplied() as needs:
            return _project_needs(state, needs), True
        case ExposureApplied() as exposure:
            return _project_exposure(state, exposure), True
        case Died() as died:
            return _project_died(state, died), True
        case ResourceHarvested() as harvested:
            return _project_harvest(state, event, harvested, production_catalog), True
        case CraftStarted() as started:
            return _project_craft_started(
                state, event, started, production_catalog
            )
        case ItemCrafted() as crafted:
            return (
                _project_item_crafted(state, event, crafted, production_catalog),
                True,
            )
        case StructureBuilt() as built:
            return (
                _project_structure_built(state, event, built, production_catalog),
                True,
            )
        case StructureRepaired() as repaired:
            return (
                _project_structure_repaired(state, event, repaired, production_catalog),
                True,
            )
        case ItemStored() as stored:
            return _project_item_stored(state, event, stored, production_catalog), True
        case SeasonChanged() as season:
            return _project_season(state, event, season, environmental_dynamics)
        case TemperatureBandChanged() as band:
            return _project_temperature_band(
                state, event, band, environmental_dynamics
            )
        case ResourceNodeDepleted() | ResourceNodeRecovered() as witness:
            return _project_node_witness(state, event, witness)
        case EnvironmentalHazardStarted() as started:
            return _project_hazard_started(state, event, started)
        case EnvironmentalHazardEnded() as ended:
            return _project_hazard_ended(state, event, ended)
        case ArtifactCreated() as created:
            return _project_artifact_created(state, event, created), True
        case ArtifactModified() as modified:
            return _project_artifact_modified(state, event, modified), True
        case ArtifactMoved() as moved_artifact:
            return _project_artifact_moved(state, event, moved_artifact), True
        case ArtifactDestroyed() as destroyed:
            return _project_artifact_destroyed(state, event, destroyed), True
        case ArtifactCopied() as copied:
            return _project_artifact_copied(state, event, copied), True
        case ArtifactAnnotated() as annotated:
            return _project_artifact_annotated(state, event, annotated), True
        case ArtifactDamaged() as damaged:
            return _project_artifact_damaged(state, event, damaged), True
        case ArtifactPartiallyLost() as partial:
            return _project_artifact_partially_lost(state, event, partial), True
        case AgentCreated() as created:
            return _project_agent_created(state, event, created)
        case AgentInitializationRecorded() as recorded:
            return _project_agent_initialization_recorded(state, event, recorded)
        case AgentEnteredWorld() as entered:
            return _project_agent_entered(state, event, entered), True
        case LifecycleStageChanged() as stage_changed:
            return _project_lifecycle_stage_changed(state, event, stage_changed)
        case KinshipEdgeRecorded() as kinship_edge:
            return _project_kinship_edge_recorded(state, event, kinship_edge)
        case RepositoryEstablished() as established:
            return _project_repository_established(state, event, established), True
        case RepositoryMemberDeposited() as deposited:
            return _project_repository_member_deposited(state, event, deposited), True
        case RepositoryMemberRetrieved() as retrieved:
            return _project_repository_member_retrieved(state, event, retrieved), True
        case RepositoryMaintained() as maintained:
            return _project_repository_maintained(state, event, maintained), True
        case RepositoryIndexed() as indexed:
            return _project_repository_indexed(state, event, indexed), True
        case RepositoryNeglected() as neglected:
            return _project_repository_neglected(state, event, neglected), True
        case _:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)



def _project_repository_established(
    state: WorldState,
    event: WorldEvent,
    details: RepositoryEstablished,
) -> WorldState:
    del event
    from world.repositories import KnowledgeRepository, RepositoryAccessMode, RepositoryStatus

    if details.repository_id in state.repositories:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED)
    created = KnowledgeRepository(
        repository_id=details.repository_id,
        location_id=details.location_id,
        founder_ids=details.founder_ids,
        established_tick=details.established_tick,
        access_mode=RepositoryAccessMode(details.access_mode),
        status=RepositoryStatus.INTACT,
        structure_id=details.structure_id,
        last_maintained_tick=details.established_tick,
    )
    repositories = dict(state.repositories)
    repositories[details.repository_id] = created
    _LOG.debug(
        "replay_apply detail_type=repository_established repository_id=%s",
        details.repository_id.value,
    )
    try:
        return rebuild_world_state(state, repositories=repositories)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_repository_member_deposited(
    state: WorldState,
    event: WorldEvent,
    details: RepositoryMemberDeposited,
) -> WorldState:
    del event
    from dataclasses import replace

    repository = state.repositories.get(details.repository_id)
    artifact = state.artifacts.get(details.artifact_id)
    if repository is None or artifact is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    updated_repo = replace(
        repository,
        member_artifact_ids=repository.member_artifact_ids + (details.artifact_id,),
    )
    updated_artifact = replace(
        artifact,
        holder_id=None,
        location_id=repository.location_id,
        custodian_repository_id=repository.repository_id,
    )
    artifacts = dict(state.artifacts)
    artifacts[details.artifact_id] = updated_artifact
    repositories = dict(state.repositories)
    repositories[details.repository_id] = updated_repo
    try:
        return rebuild_world_state(
            state, artifacts=artifacts, repositories=repositories
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_repository_member_retrieved(
    state: WorldState,
    event: WorldEvent,
    details: RepositoryMemberRetrieved,
) -> WorldState:
    del event
    from dataclasses import replace

    repository = state.repositories.get(details.repository_id)
    artifact = state.artifacts.get(details.artifact_id)
    if repository is None or artifact is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    members = tuple(
        mid for mid in repository.member_artifact_ids if mid != details.artifact_id
    )
    updated_repo = replace(repository, member_artifact_ids=members)
    if details.hold:
        updated_artifact = replace(
            artifact,
            holder_id=details.actor_id,
            location_id=None,
            custodian_repository_id=None,
        )
    else:
        updated_artifact = replace(
            artifact,
            holder_id=None,
            location_id=repository.location_id,
            custodian_repository_id=None,
        )
    artifacts = dict(state.artifacts)
    artifacts[details.artifact_id] = updated_artifact
    repositories = dict(state.repositories)
    repositories[details.repository_id] = updated_repo
    try:
        return rebuild_world_state(
            state, artifacts=artifacts, repositories=repositories
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_repository_maintained(
    state: WorldState,
    event: WorldEvent,
    details: RepositoryMaintained,
) -> WorldState:
    del event
    from dataclasses import replace
    from world.repositories import RepositoryStatus

    repository = state.repositories.get(details.repository_id)
    if repository is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    artifacts = dict(state.artifacts)
    if details.mode == "destroy":
        for member_id in repository.member_artifact_ids:
            member = artifacts[member_id]
            artifacts[member_id] = replace(
                member,
                custodian_repository_id=None,
                holder_id=None,
                location_id=repository.location_id,
            )
        updated = replace(
            repository,
            status=RepositoryStatus.DESTROYED,
            member_artifact_ids=(),
            last_maintained_tick=details.last_maintained_tick,
            neglect_streak=0,
        )
    else:
        updated = replace(
            repository,
            status=RepositoryStatus(details.next_status),
            last_maintained_tick=details.last_maintained_tick,
            neglect_streak=0,
        )
    repositories = dict(state.repositories)
    repositories[details.repository_id] = updated
    try:
        return rebuild_world_state(
            state, artifacts=artifacts, repositories=repositories
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_repository_indexed(
    state: WorldState,
    event: WorldEvent,
    details: RepositoryIndexed,
) -> WorldState:
    del event
    _LOG.debug(
        "replay_apply detail_type=repository_indexed repository_id=%s "
        "index_entry_count=%s",
        details.repository_id.value,
        details.index_entry_count,
    )
    return state


def _project_repository_neglected(
    state: WorldState,
    event: WorldEvent,
    details: RepositoryNeglected,
) -> WorldState:
    del event
    from dataclasses import replace
    from world.repositories import RepositoryStatus

    repository = state.repositories.get(details.repository_id)
    if repository is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    entries = repository.index_entries
    if details.index_entries_dropped and entries:
        ordered = tuple(sorted(entries, key=lambda item: item.entry_id))
        entries = ordered[:- details.index_entries_dropped]
    updated = replace(
        repository,
        status=RepositoryStatus(details.next_status),
        neglect_streak=details.neglect_streak,
        index_entries=entries,
    )
    repositories = dict(state.repositories)
    repositories[details.repository_id] = updated
    try:
        return rebuild_world_state(state, repositories=repositories)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _environment_mismatch(tick: int, kind: str) -> None:
    _LOG.error("environment_witness_mismatch tick=%s kind=%s", tick, kind)
    raise ProjectionError(ProjectionErrorCode.ENVIRONMENT_WITNESS_MISMATCH)


def _require_dynamics(
    event: WorldEvent, spec: object | None
) -> EnvironmentalDynamicsSpec:
    if type(spec) is not EnvironmentalDynamicsSpec:
        _environment_mismatch(event.tick, event.details.kind)
    assert spec is not None
    return spec


def _band_at(
    state: WorldState,
    location_id: EntityId,
    tick: int,
    spec: EnvironmentalDynamicsSpec,
) -> object:
    location = state.locations.get(location_id)
    weather = state.weather.get(location_id)
    if location is None or weather is None:
        return None
    rules: PhysicalRules = default_physical_rules()
    phase_offsets = rules.phase_temperature_offset
    weather_offsets = rules.weather_temperature_offset
    assert phase_offsets is not None and weather_offsets is not None
    season = spec.season_at(tick)
    ambient = round_physical(
        location.base_temperature.value
        + weather_offsets[weather.condition]
        + phase_offsets[rules.day_phase_for_tick(tick)]
        + spec.offset_for(season)
    )
    return temperature_band(ambient)


def _project_season(
    state: WorldState,
    event: WorldEvent,
    season: SeasonChanged,
    spec: object | None,
) -> tuple[WorldState, bool]:
    dynamics = _require_dynamics(event, spec)
    if (
        not dynamics.transitions_at(event.tick)
        or dynamics.season_at(event.tick) is not season.season
    ):
        _environment_mismatch(event.tick, season.kind)
    return state, True


def _project_temperature_band(
    state: WorldState,
    event: WorldEvent,
    band: TemperatureBandChanged,
    spec: object | None,
) -> tuple[WorldState, bool]:
    dynamics = _require_dynamics(event, spec)
    expected = _band_at(state, band.location_id, event.tick, dynamics)
    if expected is not band.band:
        _environment_mismatch(event.tick, band.kind)
    return state, True


def _project_node_witness(
    state: WorldState,
    event: WorldEvent,
    witness: ResourceNodeDepleted | ResourceNodeRecovered,
) -> tuple[WorldState, bool]:
    resource = state.resources.get(witness.resource_id)
    if resource is None or resource.quantity != witness.resulting_quantity:
        _environment_mismatch(event.tick, witness.kind)
    return state, False


def _project_hazard_started(
    state: WorldState,
    event: WorldEvent,
    started: EnvironmentalHazardStarted,
) -> tuple[WorldState, bool]:
    if started.location_id not in state.locations:
        _environment_mismatch(event.tick, started.kind)
    if any(
        hazard.location_id == started.location_id and hazard.kind is started.hazard_kind
        for hazard in state.active_hazards
    ):
        _environment_mismatch(event.tick, started.kind)
    record = ActiveHazard(
        started.location_id,
        started.hazard_kind,
        event.tick,
        started.duration_ticks,
    )
    if record.remaining_ticks(event.tick) != started.remaining_ticks:
        _environment_mismatch(event.tick, started.kind)
    return (
        rebuild_world_state(
            state, active_hazards=(*state.active_hazards, record)
        ),
        True,
    )


def _project_hazard_ended(
    state: WorldState,
    event: WorldEvent,
    ended: EnvironmentalHazardEnded,
) -> tuple[WorldState, bool]:
    found: ActiveHazard | None = None
    kept: list[ActiveHazard] = []
    for hazard in state.active_hazards:
        if hazard.location_id == ended.location_id and hazard.kind is ended.hazard_kind:
            found = hazard
        else:
            kept.append(hazard)
    if (
        found is None
        or ended.remaining_ticks != 0
        or event.tick != found.start_tick + found.duration_ticks - 1
    ):
        _environment_mismatch(event.tick, ended.kind)
    return rebuild_world_state(state, active_hazards=tuple(kept)), True


def _project_artifact_created(
    state: WorldState,
    event: WorldEvent,
    details: ArtifactCreated,
) -> WorldState:
    if details.artifact_id in state.artifacts:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if event.actor_id is None or event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if (
        details.resulting_location_id is not None
        and details.resulting_location_id not in state.locations
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if (
        details.resulting_holder_id is not None
        and details.resulting_holder_id not in state.bodies
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    # Content tokens are checkpoint-owned; folds create an empty face.
    created = InformationArtifact(
        artifact_id=details.artifact_id,
        kind=details.artifact_kind,
        author_id=details.author_id,
        created_tick=event.tick,
        content=ArtifactContent(),
        content_revision=details.content_revision,
        location_id=details.resulting_location_id,
        holder_id=details.resulting_holder_id,
    )
    artifacts = dict(state.artifacts)
    artifacts[details.artifact_id] = created
    try:
        return rebuild_world_state(state, artifacts=artifacts)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_artifact_modified(
    state: WorldState,
    event: WorldEvent,
    details: ArtifactModified,
) -> WorldState:
    del event  # tick unused; revision/placement come from the detail
    prior = state.artifacts.get(details.artifact_id)
    if prior is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if (
        details.resulting_location_id is not None
        and details.resulting_location_id not in state.locations
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if (
        details.resulting_holder_id is not None
        and details.resulting_holder_id not in state.bodies
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    updated = replace(
        prior,
        kind=details.artifact_kind,
        content_revision=details.content_revision,
        location_id=details.resulting_location_id,
        holder_id=details.resulting_holder_id,
    )
    artifacts = dict(state.artifacts)
    artifacts[details.artifact_id] = updated
    try:
        return rebuild_world_state(state, artifacts=artifacts)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_artifact_moved(
    state: WorldState,
    event: WorldEvent,
    details: ArtifactMoved,
) -> WorldState:
    del event
    prior = state.artifacts.get(details.artifact_id)
    if prior is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if (
        details.resulting_location_id is not None
        and details.resulting_location_id not in state.locations
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if (
        details.resulting_holder_id is not None
        and details.resulting_holder_id not in state.bodies
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    updated = replace(
        prior,
        kind=details.artifact_kind,
        content_revision=details.content_revision,
        location_id=details.resulting_location_id,
        holder_id=details.resulting_holder_id,
    )
    artifacts = dict(state.artifacts)
    artifacts[details.artifact_id] = updated
    try:
        return rebuild_world_state(state, artifacts=artifacts)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_artifact_destroyed(
    state: WorldState,
    event: WorldEvent,
    details: ArtifactDestroyed,
) -> WorldState:
    del event
    prior = state.artifacts.get(details.artifact_id)
    if prior is None or prior.content_revision != details.content_revision:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    artifacts = dict(state.artifacts)
    if details.tombstone:
        from world.artifacts import RecordIntegrity

        artifacts[details.artifact_id] = replace(
            prior,
            integrity=RecordIntegrity.DESTROYED,
            location_id=None,
            holder_id=None,
        )
    else:
        del artifacts[details.artifact_id]
    try:
        return rebuild_world_state(state, artifacts=artifacts)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_artifact_copied(
    state: WorldState,
    event: WorldEvent,
    details: ArtifactCopied,
) -> WorldState:
    from world.artifacts import DurableRecordGenre, RecordIntegrity

    if details.child_artifact_id in state.artifacts:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    parent = state.artifacts.get(details.parent_artifact_id)
    if parent is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if event.actor_id is None or event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    created = InformationArtifact(
        artifact_id=details.child_artifact_id,
        kind=parent.kind,
        author_id=event.actor_id,
        created_tick=event.tick,
        content=ArtifactContent(),
        content_revision=details.content_revision,
        location_id=event.actor_id and state.bodies[event.actor_id].location_id,
        holder_id=None,
        record_genre=DurableRecordGenre(details.record_genre),
        parent_artifact_id=details.parent_artifact_id,
        source_artifact_id=details.source_artifact_id,
        copy_generation=details.copy_generation,
        integrity=RecordIntegrity.INTACT,
    )
    artifacts = dict(state.artifacts)
    artifacts[details.child_artifact_id] = created
    _LOG.debug(
        "replay_apply detail_type=artifact_copied artifact_id=%s",
        details.child_artifact_id.value,
    )
    try:
        return rebuild_world_state(state, artifacts=artifacts)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_artifact_annotated(
    state: WorldState,
    event: WorldEvent,
    details: ArtifactAnnotated,
) -> WorldState:
    del event
    from world.artifacts import RecordIntegrity

    prior = state.artifacts.get(details.artifact_id)
    if prior is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    updated = replace(
        prior,
        content_revision=details.content_revision,
        annotation_revisions=details.annotation_revisions,
        integrity=RecordIntegrity(details.integrity),
    )
    artifacts = dict(state.artifacts)
    artifacts[details.artifact_id] = updated
    _LOG.debug(
        "replay_apply detail_type=artifact_annotated artifact_id=%s",
        details.artifact_id.value,
    )
    try:
        return rebuild_world_state(state, artifacts=artifacts)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_artifact_damaged(
    state: WorldState,
    event: WorldEvent,
    details: ArtifactDamaged,
) -> WorldState:
    del event
    from world.artifacts import RecordIntegrity

    prior = state.artifacts.get(details.artifact_id)
    if prior is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    updated = replace(
        prior,
        content_revision=details.content_revision,
        integrity=RecordIntegrity(details.next_integrity),
        lost_mark_count=prior.lost_mark_count + details.lost_mark_count_delta,
    )
    artifacts = dict(state.artifacts)
    artifacts[details.artifact_id] = updated
    _LOG.debug(
        "replay_apply detail_type=artifact_damaged artifact_id=%s",
        details.artifact_id.value,
    )
    try:
        return rebuild_world_state(state, artifacts=artifacts)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_artifact_partially_lost(
    state: WorldState,
    event: WorldEvent,
    details: ArtifactPartiallyLost,
) -> WorldState:
    del event
    from world.artifacts import RecordIntegrity

    prior = state.artifacts.get(details.artifact_id)
    if prior is None:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    marks = prior.content.marks[: details.marks_remaining]
    updated = replace(
        prior,
        content=ArtifactContent(marks=marks, relations=prior.content.relations),
        content_revision=details.content_revision,
        integrity=RecordIntegrity(details.integrity),
        lost_mark_count=details.lost_mark_count,
    )
    artifacts = dict(state.artifacts)
    artifacts[details.artifact_id] = updated
    _LOG.debug(
        "replay_apply detail_type=artifact_partially_lost artifact_id=%s",
        details.artifact_id.value,
    )
    try:
        return rebuild_world_state(state, artifacts=artifacts)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_agent_created(
    state: WorldState,
    event: WorldEvent,
    details: AgentCreated,
) -> tuple[WorldState, bool]:
    """Identity reservation: body must not exist yet; no WorldState mutation."""
    if details.body_id in state.bodies:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if event.actor_id is not None and event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    return state, False


def _project_agent_initialization_recorded(
    state: WorldState,
    event: WorldEvent,
    details: AgentInitializationRecorded,
) -> tuple[WorldState, bool]:
    """Provenance witness only — body placement stays on AgentEnteredWorld."""
    del event, details
    return state, False


def _project_agent_entered(
    state: WorldState,
    event: WorldEvent,
    details: AgentEnteredWorld,
) -> WorldState:
    """Place a new living body at the entry location with deterministic defaults."""
    del event
    if details.body_id in state.bodies:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.location_id not in state.locations:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    body = default_entrant_body(
        body_id=details.body_id, location_id=details.location_id
    )
    bodies = dict(state.bodies)
    bodies[details.body_id] = body
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_lifecycle_stage_changed(
    state: WorldState,
    event: WorldEvent,
    details: LifecycleStageChanged,
) -> tuple[WorldState, bool]:
    """Stage lives on engine lifecycle records; fold validates body presence."""
    del event
    if details.body_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    return state, False


def _project_kinship_edge_recorded(
    state: WorldState,
    event: WorldEvent,
    details: KinshipEdgeRecorded,
) -> tuple[WorldState, bool]:
    """Kinship graph lives on the engine; fold is a schema-gated no-op on WorldState."""
    del details
    if event.schema_version not in {
        EVENT_SCHEMA_REPLAY_V11,
        EVENT_SCHEMA_REPLAY_V12,
        EVENT_SCHEMA_REPLAY_V13,
    }:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    return state, False


def _apply_legacy_transfer(state: WorldState, event: WorldEvent) -> WorldState:
    match event.details:
        case Taken(item_id=item_id, resulting_holder_id=holder_id):
            return _project_take(state, event, item_id=item_id, holder_id=holder_id)
        case Dropped(item_id=item_id, resulting_location_id=location_id):
            return _project_drop(state, event, item_id=item_id, location_id=location_id)
        case Given(
            recipient_id=recipient_id,
            item_id=item_id,
            resulting_holder_id=holder_id,
        ):
            return _project_give(
                state,
                event,
                recipient_id=recipient_id,
                item_id=item_id,
                holder_id=holder_id,
            )
        case _:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)


def _project_take(
    state: WorldState,
    event: WorldEvent,
    *,
    item_id: EntityId,
    holder_id: EntityId | None,
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if holder_id is None or holder_id != actor_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    item = state.items[item_id]
    if item.location_id is None or item.holder_id is not None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    actor = state.bodies[actor_id]
    if item_id in actor.inventory:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=None, holder_id=actor_id)
    bodies[actor_id] = _copy_body(actor, inventory=(*actor.inventory, item_id))
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_drop(
    state: WorldState,
    event: WorldEvent,
    *,
    item_id: EntityId,
    location_id: EntityId | None,
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if location_id is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if location_id not in state.locations:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    if location_id != actor.location_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    item = state.items[item_id]
    if item.holder_id != actor_id or item_id not in actor.inventory:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=location_id, holder_id=None)
    bodies[actor_id] = _copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_give(
    state: WorldState,
    event: WorldEvent,
    *,
    recipient_id: EntityId,
    item_id: EntityId,
    holder_id: EntityId | None,
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if holder_id is None or holder_id != recipient_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if recipient_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    recipient = state.bodies[recipient_id]
    item = state.items[item_id]
    if item.holder_id != actor_id or item_id not in actor.inventory:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if actor_id == recipient_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=None, holder_id=recipient_id)
    bodies[actor_id] = _copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    bodies[recipient_id] = _copy_body(
        recipient, inventory=(*recipient.inventory, item_id)
    )
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_move(state: WorldState, event: WorldEvent, details: Moved) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.resulting_location_id is None or details.resulting_fatigue is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.resulting_location_id != details.destination_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.destination_id not in state.locations:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        actor,
        location_id=details.resulting_location_id,
        fatigue=Fatigue(details.resulting_fatigue),
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_search_success(
    state: WorldState, event: WorldEvent, details: Searched
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if (
        details.target_id is None
        or details.created_item_id is None
        or details.resulting_resource_quantity is None
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.target_id not in state.resources:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if details.created_item_id in state.items:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    actor = state.bodies[actor_id]
    resource = state.resources[details.target_id]
    item_kind = _ITEM_KIND_FOR_RESOURCE.get(resource.kind)
    if item_kind is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    created = Item(
        entity_id=details.created_item_id,
        name=f"foraged-{resource.kind.value}",
        kind=item_kind,
        load=ItemLoad(1),
        location_id=actor.location_id,
        holder_id=None,
    )
    resources = dict(state.resources)
    items = dict(state.items)
    resources[details.target_id] = copy_resource(
        resource, quantity=details.resulting_resource_quantity
    )
    items[details.created_item_id] = created
    try:
        return rebuild_world_state(state, items=items, resources=resources)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_eat(state: WorldState, event: WorldEvent, details: Eaten) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.resulting_hunger is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    if details.item_id not in actor.inventory:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    items = dict(state.items)
    bodies = dict(state.bodies)
    del items[details.item_id]
    bodies[actor_id] = copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != details.item_id),
        hunger=Hunger(details.resulting_hunger),
    )
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_drink(state: WorldState, event: WorldEvent, details: Drunk) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.consumed_item is None or details.resulting_thirst is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    actor = state.bodies[actor_id]
    bodies = dict(state.bodies)
    items = dict(state.items)
    resources = dict(state.resources)
    if details.consumed_item:
        if details.source_id not in state.items:
            raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
        if details.source_id not in actor.inventory:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
        del items[details.source_id]
        bodies[actor_id] = copy_body(
            actor,
            inventory=tuple(
                owned for owned in actor.inventory if owned != details.source_id
            ),
            thirst=Thirst(details.resulting_thirst),
        )
    else:
        if details.source_id not in state.resources:
            raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
        if details.resulting_resource_quantity is None:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
        resource = state.resources[details.source_id]
        resources[details.source_id] = copy_resource(
            resource, quantity=details.resulting_resource_quantity
        )
        bodies[actor_id] = copy_body(actor, thirst=Thirst(details.resulting_thirst))
    try:
        return rebuild_world_state(
            state, items=items, bodies=bodies, resources=resources
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_sleep(state: WorldState, event: WorldEvent, details: Slept) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.resulting_fatigue is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    actor = state.bodies[actor_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(actor, fatigue=Fatigue(details.resulting_fatigue))
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_help(state: WorldState, event: WorldEvent, details: Helped) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.target_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if (
        details.resulting_target_health is None
        or details.resulting_helper_fatigue is None
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    helper = state.bodies[actor_id]
    target = state.bodies[details.target_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        helper, fatigue=Fatigue(details.resulting_helper_fatigue)
    )
    bodies[details.target_id] = copy_body(
        target, health=Health(details.resulting_target_health)
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_feed(state: WorldState, event: WorldEvent, details: Fed) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.target_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if details.item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    helper = state.bodies[actor_id]
    target = state.bodies[details.target_id]
    items = dict(state.items)
    del items[details.item_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        helper,
        inventory=tuple(
            owned for owned in helper.inventory if owned != details.item_id
        ),
    )
    if details.item_kind == "food":
        if details.resulting_target_hunger is None:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
        bodies[details.target_id] = copy_body(
            target, hunger=Hunger(details.resulting_target_hunger)
        )
    elif details.item_kind == "water":
        if details.resulting_target_thirst is None:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
        bodies[details.target_id] = copy_body(
            target, thirst=Thirst(details.resulting_target_thirst)
        )
    else:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_transport(
    state: WorldState, event: WorldEvent, details: Transported
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.target_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if details.resulting_helper_fatigue is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    helper = state.bodies[actor_id]
    target = state.bodies[details.target_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        helper,
        location_id=details.destination_id,
        fatigue=Fatigue(details.resulting_helper_fatigue),
    )
    bodies[details.target_id] = copy_body(
        target, location_id=details.destination_id
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_attack_hit(
    state: WorldState, event: WorldEvent, details: Attacked
) -> WorldState:
    if event.actor_id is None or event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.target_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if details.resulting_target_health is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    target = state.bodies[details.target_id]
    bodies = dict(state.bodies)
    resulting = details.resulting_target_health
    if resulting <= 0.0:
        # Match live attack application: lethal hits flip life status atomically
        # before the separate Died event is projected.
        bodies[details.target_id] = copy_body(
            target,
            health=Health(0.0),
            life_status=LifeStatus.DEAD,
        )
    else:
        bodies[details.target_id] = copy_body(target, health=Health(resulting))
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_flee_success(
    state: WorldState, event: WorldEvent, details: Fled
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.destination_id is None or details.resulting_fatigue is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.destination_id not in state.locations:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        actor,
        location_id=details.destination_id,
        fatigue=Fatigue(details.resulting_fatigue),
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_weather(state: WorldState, details: WeatherChanged) -> WorldState:
    if details.location_id not in state.weather:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    weather = dict(state.weather)
    current = state.weather[details.location_id]
    weather[details.location_id] = copy_weather(current, condition=details.condition)
    try:
        return rebuild_world_state(state, weather=weather)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_regeneration(
    state: WorldState, details: ResourceRegenerated
) -> WorldState:
    if details.resource_id not in state.resources:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    resource = state.resources[details.resource_id]
    resources = dict(state.resources)
    resources[details.resource_id] = copy_resource(
        resource, quantity=details.resulting_quantity
    )
    try:
        return rebuild_world_state(state, resources=resources)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_needs(state: WorldState, details: NeedsApplied) -> WorldState:
    if details.body_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    body = state.bodies[details.body_id]
    bodies = dict(state.bodies)
    bodies[details.body_id] = copy_body(
        body,
        hunger=Hunger(details.resulting_hunger),
        thirst=Thirst(details.resulting_thirst),
        fatigue=Fatigue(details.resulting_fatigue),
        health=Health(details.resulting_health),
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_exposure(state: WorldState, details: ExposureApplied) -> WorldState:
    if details.body_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    body = state.bodies[details.body_id]
    bodies = dict(state.bodies)
    bodies[details.body_id] = copy_body(
        body,
        temperature=TemperatureCelsius(details.resulting_temperature),
        health=Health(details.resulting_health),
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_died(state: WorldState, details: Died) -> WorldState:
    if details.body_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    body = state.bodies[details.body_id]
    bodies = dict(state.bodies)
    bodies[details.body_id] = copy_body(
        body,
        health=Health(0.0),
        life_status=LifeStatus.DEAD,
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


    jobs = dict(state.production_jobs)
    jobs.pop(details.body_id, None)
    try:
        return rebuild_world_state(state, bodies=bodies, production_jobs=jobs)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _require_catalog(
    catalog: ProductionCatalog | None, recipe_id: object
) -> ProductionCatalog:
    if catalog is None or type(recipe_id).__name__ != "RecipeId":
        _reject_catalog(catalog)
    recipe = catalog.recipe(recipe_id)  # type: ignore[union-attr, arg-type]
    if recipe is None:
        _reject_catalog(catalog)
    return catalog  # type: ignore[return-value]


def _reject_catalog(catalog: ProductionCatalog | None) -> None:
    ids = (
        ()
        if catalog is None
        else tuple(item.recipe_id.value for item in catalog.recipes)
    )
    _LOG.error("production_catalog_mismatch digest=%s", production_catalog_digest(ids))
    raise ProjectionError(ProjectionErrorCode.CATALOG_MISMATCH)


def _drop_items(
    state: WorldState, actor_id: EntityId, item_ids: tuple[EntityId, ...]
) -> tuple[dict[EntityId, Item], dict[EntityId, AgentBody]]:
    items = dict(state.items)
    bodies = dict(state.bodies)
    dropping = set(item_ids)
    for item_id in item_ids:
        if item_id not in items:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
        del items[item_id]
    actor = bodies[actor_id]
    bodies[actor_id] = copy_body(
        actor,
        inventory=tuple(
            item_id for item_id in actor.inventory if item_id not in dropping
        ),
    )
    return items, bodies


def _project_harvest(
    state: WorldState,
    event: WorldEvent,
    details: ResourceHarvested,
    catalog: ProductionCatalog | None,
) -> WorldState:
    _require_catalog(catalog, details.recipe_id)
    assert catalog is not None
    recipe = catalog.recipe(details.recipe_id)
    assert recipe is not None
    if details.resource_id not in state.resources:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    resource = state.resources[details.resource_id]
    resources = dict(state.resources)
    resources[details.resource_id] = copy_resource(
        resource, quantity=details.resulting_resource_quantity
    )
    items = dict(state.items)
    bodies = dict(state.bodies)
    if details.success:
        if event.actor_id is None or event.actor_id not in bodies:
            raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
        if details.created_item_id is None or type(recipe.output) is not ItemProduct:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
        created = Item(
            entity_id=details.created_item_id,
            name=recipe.output.name,
            kind=recipe.output.item_kind,
            load=recipe.output.load,
            holder_id=event.actor_id,
        )
        items[created.entity_id] = created
        actor = bodies[event.actor_id]
        bodies[event.actor_id] = copy_body(
            actor, inventory=(*actor.inventory, created.entity_id)
        )
    try:
        return rebuild_world_state(
            state, items=items, resources=resources, bodies=bodies
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_craft_started(
    state: WorldState,
    event: WorldEvent,
    details: CraftStarted,
    catalog: ProductionCatalog | None,
) -> tuple[WorldState, bool]:
    _require_catalog(catalog, details.recipe_id)
    if not details.success:
        return state, False
    if event.actor_id is None or event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    items, bodies = _drop_items(state, event.actor_id, details.consumed_item_ids)
    jobs = dict(state.production_jobs)
    if details.duration_ticks > 1:
            jobs[event.actor_id] = ProductionJob(
                actor_id=event.actor_id,
                recipe_id=details.recipe_id,
                due_tick=event.tick + 1,
                created_item_id=EntityId(event.request_id.value),
                duration_ticks=details.duration_ticks,
            )
    try:
        return (
            rebuild_world_state(
                state, items=items, bodies=bodies, production_jobs=jobs
            ),
            True,
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_item_crafted(
    state: WorldState,
    event: WorldEvent,
    details: ItemCrafted,
    catalog: ProductionCatalog | None,
) -> WorldState:
    catalog = _require_catalog(catalog, details.recipe_id)
    recipe = catalog.recipe(details.recipe_id)
    assert recipe is not None
    if type(recipe.output) is not ItemProduct:
        _reject_catalog(catalog)
    holder = details.resulting_holder_id
    if holder not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    created = Item(
        entity_id=details.created_item_id,
        name=recipe.output.name,  # type: ignore[union-attr]
        kind=recipe.output.item_kind,  # type: ignore[union-attr]
        load=recipe.output.load,  # type: ignore[union-attr]
        holder_id=holder,
    )
    items = dict(state.items)
    items[created.entity_id] = created
    bodies = dict(state.bodies)
    actor = bodies[holder]
    bodies[holder] = copy_body(actor, inventory=(*actor.inventory, created.entity_id))
    jobs = dict(state.production_jobs)
    jobs.pop(holder, None)
    marks = dict(state.tool_marks)
    role = recipe.output.tool_role  # type: ignore[union-attr]
    if role is not None:
        marks[created.entity_id] = ToolMark(created.entity_id, role)
    try:
        return rebuild_world_state(
            state, items=items, bodies=bodies, production_jobs=jobs, tool_marks=marks
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_structure_built(
    state: WorldState,
    event: WorldEvent,
    details: StructureBuilt,
    catalog: ProductionCatalog | None,
) -> WorldState:
    _require_catalog(catalog, details.recipe_id)
    if event.actor_id is None or event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    items, bodies = _drop_items(state, event.actor_id, (details.consumed_item_id,))
    structures = dict(state.structures)
    structures[details.structure_id] = Structure(
        entity_id=details.structure_id,
        location_id=details.location_id,
        kind=StructureKind.SHELTER,
        integrity=details.resulting_integrity,
        stored_quantity=0,
    )
    try:
        return rebuild_world_state(
            state, items=items, bodies=bodies, structures=structures
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_structure_repaired(
    state: WorldState,
    event: WorldEvent,
    details: StructureRepaired,
    catalog: ProductionCatalog | None,
) -> WorldState:
    _require_catalog(catalog, details.recipe_id)
    if event.actor_id is None or details.structure_id not in state.structures:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    items, bodies = _drop_items(state, event.actor_id, (details.consumed_item_id,))
    prior = state.structures[details.structure_id]
    structures = dict(state.structures)
    structures[prior.entity_id] = Structure(
        entity_id=prior.entity_id,
        location_id=prior.location_id,
        kind=prior.kind,
        integrity=details.resulting_integrity,
        stored_quantity=prior.stored_quantity,
    )
    try:
        return rebuild_world_state(
            state, items=items, bodies=bodies, structures=structures
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_item_stored(
    state: WorldState,
    event: WorldEvent,
    details: ItemStored,
    catalog: ProductionCatalog | None,
) -> WorldState:
    _require_catalog(catalog, details.recipe_id)
    if event.actor_id is None or event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    items, bodies = _drop_items(state, event.actor_id, (details.consumed_item_id,))
    structures = dict(state.structures)
    existing = structures.get(details.structure_id)
    if existing is None:
        structures[details.structure_id] = Structure(
            entity_id=details.structure_id,
            location_id=state.bodies[event.actor_id].location_id,
            kind=StructureKind.STORE,
            integrity=1.0,
            stored_quantity=details.resulting_stored_quantity,
        )
    else:
        structures[existing.entity_id] = Structure(
            entity_id=existing.entity_id,
            location_id=existing.location_id,
            kind=existing.kind,
            integrity=existing.integrity,
            stored_quantity=details.resulting_stored_quantity,
        )
    try:
        return rebuild_world_state(
            state, items=items, bodies=bodies, structures=structures
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _copy_body(body: AgentBody, *, inventory: tuple[EntityId, ...]) -> AgentBody:
    return copy_body(body, inventory=inventory)
