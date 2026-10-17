"""Private deterministic perception projector.

Visibility policy:
- Always expose self, hour/day-phase, visibility modifier, current weather,
  current location, and adjacent exits.
- Ground items, resource nodes, structures, ground artifacts, and other bodies
  appear only when effective visibility is at least
  ``CONTENT_VISIBILITY_THRESHOLD``.
- Held inventory and self-held artifacts remain visible below the content
  threshold. Foreign held artifacts are never projected.
- Dead registered observers still receive self/time/environment observations.
- Physical target validation is not visibility-gated (handled elsewhere).
- Prior-tick occurrences are redacted by audience using event occurrence context.
- Communication text is claim-only and delivered to speaker and private recipients.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final, cast

from world._state import WorldState
from world.artifacts import InformationArtifact, RecordIntegrity
from world.environment import (
    EnvironmentalDynamicsSpec,
    HazardKind,
    Season,
    TemperatureBand,
    temperature_band,
)
from world.events import (
    ArtifactAnnotated,
    ArtifactCopied,
    ArtifactCreated,
    ArtifactDamaged,
    ArtifactDestroyed,
    ArtifactModified,
    ArtifactMoved,
    ArtifactPartiallyLost,
    Asked,
    CommitmentDeclared,
    CorpseCustodyOpened,
    CraftStarted,
    ExchangeCompleted,
    ExchangeProposed,
    ExchangeWithdrawn,
    ExperimentResolved,
    Given,
    ItemCrafted,
    ItemStored,
    JourneyArrived,
    JourneyEnded,
    JourneyStarted,
    PossessionClaimAsserted,
    ProjectAbandoned,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    ProjectShortage,
    PublicGoodBenefit,
    PublicGoodMaintained,
    PublicGoodOpposed,
    ResourceHarvested,
    StructureBuilt,
    StructureRepaired,
    TakenFromCorpse,
    Talked,
    Told,
    WorldEvent,
    require_replayable_event,
)
from world.identifiers import EntityId, WorldId
from world.models import Item, LifeStatus, copy_body
from world.observations import (
    CONTENT_VISIBILITY_THRESHOLD,
    ExchangeVisibleHolding,
    Observation,
    ObservationAudienceRole,
    ObservationContext,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedArtifact,
    ObservedCollectiveProject,
    ObservedCommunication,
    ObservedDependencyNeeds,
    ObservedItem,
    ObservedItemPlacement,
    ObservedJourney,
    ObservedJourneyPhase,
    ObservedKinshipVisible,
    ObservedLifecycle,
    ObservedLocation,
    ObservedOccurrence,
    ObservedProjectContribution,
    ObservedRegionalContext,
    ObservedRepository,
    ObservedResource,
    ObservedStructure,
    VisibleBody,
    VisibleExit,
    coarse_health_for,
    observed_self_from_body,
)
from world.values import WeatherCondition, round_physical

_LOG: Final[logging.Logger] = logging.getLogger("world._perception")
_PRODUCTION_DETAIL_TYPES: Final[frozenset[type]] = frozenset(
    {
        ResourceHarvested,
        CraftStarted,
        ItemCrafted,
        StructureBuilt,
        StructureRepaired,
        ItemStored,
    }
)
_ARTIFACT_DETAIL_TYPES: Final[frozenset[type]] = frozenset(
    {
        ArtifactCreated,
        ArtifactModified,
        ArtifactMoved,
        ArtifactDestroyed,
        ArtifactCopied,
        ArtifactAnnotated,
        ArtifactDamaged,
        ArtifactPartiallyLost,
    }
)

__all__: list[str] = ["PerceptionService", "project_observations"]


class PerceptionService:
    """Sole objective-to-subjective projector for agent observations.

    Deterministic. Accepts world authority inputs only from approved
    simulation and private-world callers. Production debug lines record recipe
    ids and structure counts, never item names.
    """

    def __init__(
        self,
        *,
        durable_perception_mode: str | None = None,
        repository_perception_mode: str | None = None,
        possession_succession_active: bool = False,
        structured_commitments_active: bool = False,
        subjective_valuation_active: bool = False,
        collective_projects_active: bool = False,
        public_goods_active: bool = False,
    ) -> None:
        if durable_perception_mode is not None and durable_perception_mode not in {
            "marks_and_meta",
            "marks_only",
        }:
            raise ValueError(
                "durable_perception_mode must be marks_and_meta, marks_only, or None"
            )
        if (
            repository_perception_mode is not None
            and repository_perception_mode
            not in {"container_and_meta", "container_only"}
        ):
            raise ValueError(
                "repository_perception_mode must be container_and_meta, "
                "container_only, or None"
            )
        if type(possession_succession_active) is not bool:
            raise TypeError("possession_succession_active must be bool")
        if type(structured_commitments_active) is not bool:
            raise TypeError("structured_commitments_active must be bool")
        if type(subjective_valuation_active) is not bool:
            raise TypeError("subjective_valuation_active must be bool")
        if type(collective_projects_active) is not bool:
            raise TypeError("collective_projects_active must be bool")
        if type(public_goods_active) is not bool:
            raise TypeError("public_goods_active must be bool")
        self._durable_perception_mode = durable_perception_mode
        self._repository_perception_mode = repository_perception_mode
        self._possession_succession_active = possession_succession_active
        self._structured_commitments_active = structured_commitments_active
        self._subjective_valuation_active = subjective_valuation_active
        self._collective_projects_active = collective_projects_active
        self._public_goods_active = public_goods_active

    def project(
        self,
        *,
        world_id: WorldId,
        state: WorldState,
        observer_ids: Sequence[EntityId],
        context: ObservationContext,
        prior_events: Sequence[WorldEvent] = (),
        environmental_dynamics: object | None = None,
    ) -> tuple[Observation, ...]:
        """Project exactly one detached observation per ordered observer id."""
        if type(world_id) is not WorldId:
            raise TypeError("PerceptionService.project requires WorldId")
        if type(state) is not WorldState:
            raise TypeError("PerceptionService.project requires WorldState")
        if type(context) is not ObservationContext:
            raise TypeError("PerceptionService.project requires ObservationContext")
        if (
            environmental_dynamics is not None
            and type(environmental_dynamics) is not EnvironmentalDynamicsSpec
        ):
            raise TypeError(
                "PerceptionService.project environmental_dynamics must be "
                "EnvironmentalDynamicsSpec or None"
            )
        observers = _copy_observer_ids(observer_ids)
        events = _copy_prior_events(prior_events, observation_tick=context.tick)
        for observer_id in observers:
            if observer_id not in state.bodies:
                raise ValueError(
                    f"observer body {observer_id.value!r} is missing from world state"
                )
        return tuple(
            _project_one(
                world_id=world_id,
                state=state,
                observer_id=observer_id,
                context=context,
                prior_events=events,
                environmental_dynamics=environmental_dynamics,
                durable_perception_mode=self._durable_perception_mode,
                repository_perception_mode=self._repository_perception_mode,
                possession_succession_active=self._possession_succession_active,
                structured_commitments_active=self._structured_commitments_active,
                subjective_valuation_active=self._subjective_valuation_active,
                collective_projects_active=self._collective_projects_active,
                public_goods_active=self._public_goods_active,
            )
            for observer_id in observers
        )


def project_observations(
    *,
    world_id: WorldId,
    state: WorldState,
    observer_ids: Sequence[EntityId],
    context: ObservationContext | None = None,
    prior_events: Sequence[WorldEvent] = (),
    environmental_dynamics: object | None = None,
    durable_perception_mode: str | None = None,
    repository_perception_mode: str | None = None,
    structured_commitments_active: bool = False,
    subjective_valuation_active: bool = False,
    collective_projects_active: bool = False,
    public_goods_active: bool = False,
) -> tuple[Observation, ...]:
    """Compatibility wrapper around :class:`PerceptionService`."""
    resolved = context if context is not None else ObservationContext(tick=0)
    return PerceptionService(
        durable_perception_mode=durable_perception_mode,
        repository_perception_mode=repository_perception_mode,
        structured_commitments_active=structured_commitments_active,
        subjective_valuation_active=subjective_valuation_active,
        collective_projects_active=collective_projects_active,
        public_goods_active=public_goods_active,
    ).project(
        world_id=world_id,
        state=state,
        observer_ids=observer_ids,
        context=resolved,
        prior_events=prior_events,
        environmental_dynamics=environmental_dynamics,
    )


def _project_one(
    *,
    world_id: WorldId,
    state: WorldState,
    observer_id: EntityId,
    context: ObservationContext,
    prior_events: tuple[WorldEvent, ...],
    environmental_dynamics: object | None,
    durable_perception_mode: str | None = None,
    repository_perception_mode: str | None = None,
    possession_succession_active: bool = False,
    structured_commitments_active: bool = False,
    subjective_valuation_active: bool = False,
    collective_projects_active: bool = False,
    public_goods_active: bool = False,
) -> Observation:
    body = state.bodies[observer_id]
    location_id = body.location_id
    location = state.locations.get(location_id)
    weather = state.weather.get(location_id)
    condition = weather.condition if weather is not None else WeatherCondition.CLEAR
    visibility = 1.0
    if location is not None:
        visibility = context.physical_rules.effective_visibility(
            location_visibility=location.visibility_factor.value,
            phase=context.day_phase,
            condition=condition,
        )
    content_visible = visibility >= CONTENT_VISIBILITY_THRESHOLD
    occurrences, communications = _project_event_window(
        observer_id=observer_id,
        location_id=location_id,
        content_visible=content_visible,
        prior_events=prior_events,
        state=state,
        structured_commitments_active=structured_commitments_active,
        subjective_valuation_active=subjective_valuation_active,
        collective_projects_active=collective_projects_active,
        public_goods_active=public_goods_active,
    )
    structures = _sorted_structures(state, location_id) if content_visible else ()
    artifacts = _sorted_artifacts(
        state,
        observer_id=observer_id,
        location_id=location_id,
        include_ground=content_visible,
        durable_perception_mode=durable_perception_mode,
        include_custodian=(repository_perception_mode == "container_and_meta"),
    )
    repositories = (
        _sorted_repositories(
            state,
            location_id=location_id,
            perception_mode=repository_perception_mode,
        )
        if content_visible and repository_perception_mode is not None
        else ()
    )
    recipes = [
        occurrence.public_facts["recipe_id"]
        for occurrence in occurrences
        if "recipe_id" in occurrence.public_facts
    ]
    if structures or recipes:
        _LOG.debug(
            "production_observed recipe_id=%s structure_count=%s",
            recipes[0] if recipes else "-",
            len(structures),
        )
    _LOG.debug("artifacts_observed count=%s", len(artifacts))
    _LOG.debug("observed_repository_count=%s", len(repositories))
    if collective_projects_active and content_visible:
        collective_projects = _sorted_collective_projects(
            state, location_id, public_goods_active=public_goods_active
        )
        _LOG.debug(
            "collective_projects_perceived location_id=%s count=%s",
            location_id.value,
            len(collective_projects),
        )
        if public_goods_active:
            _LOG.debug(
                "public_goods_perceived location_id=%s act_count=%s",
                location_id.value,
                sum(len(project.public_acts) for project in collective_projects),
            )
    elif collective_projects_active:
        collective_projects = ()
        _LOG.debug("collective_projects_hidden reason=content_hidden")
        if public_goods_active:
            _LOG.debug("public_goods_hidden reason=content_hidden")
    else:
        collective_projects = ()
    season, band, kinds = _present_environment(
        state=state,
        location_id=location_id,
        context=context,
        condition=condition,
        spec=environmental_dynamics,
    )
    return Observation(
        world_id=world_id,
        observer_id=observer_id,
        revision=state.revision,
        tick=context.tick,
        self_body=observed_self_from_body(
            copy_body(body),
            lifecycle=_lifecycle_for(context, observer_id),
            kinship_visible=_kinship_self_for(context, observer_id),
            dependency_needs=_dependency_needs_for(context, observer_id),
            journey=_observed_journey(state, observer_id, tick=context.tick),
        ),
        locations=_sorted_locations(state, location_id),
        items=_sorted_items(
            state,
            observer_id=observer_id,
            location_id=location_id,
            include_ground=content_visible,
            possession_succession_active=possession_succession_active,
        ),
        resources=(_sorted_resources(state, location_id) if content_visible else ()),
        structures=structures,
        artifacts=artifacts,
        repositories=repositories,
        collective_projects=collective_projects,
        exits=_sorted_exits(state, location_id, physical_rules=context.physical_rules),
        visible_bodies=(
            _sorted_visible_bodies(state, location_id, observer_id, context=context)
            if content_visible
            else ()
        ),
        occurrences=occurrences,
        communications=communications,
        hour=context.hour,
        day_phase=context.day_phase,
        visibility=visibility,
        weather_condition=condition,
        season=season,
        temperature_band=band,
        hazard_kinds=kinds,
        exchange_visible_holdings=(
            _exchange_visible_holdings(state, observer_id, location_id)
            if subjective_valuation_active
            else None
        ),
        regional_context=_regional_context(state, location_id),
    )


def _present_environment(
    *,
    state: WorldState,
    location_id: EntityId,
    context: ObservationContext,
    condition: WeatherCondition,
    spec: object | None,
) -> tuple[Season | None, TemperatureBand | None, tuple[HazardKind, ...] | None]:
    if spec is None:
        return None, None, None
    if type(spec) is not EnvironmentalDynamicsSpec:
        raise TypeError(
            "environmental dynamics must be EnvironmentalDynamicsSpec or None"
        )
    location = state.locations.get(location_id)
    season = spec.season_at(context.tick)
    band = None
    if location is not None:
        rules = context.physical_rules
        phase_offsets = rules.phase_temperature_offset
        weather_offsets = rules.weather_temperature_offset
        assert phase_offsets is not None and weather_offsets is not None
        ambient = round_physical(
            location.base_temperature.value
            + weather_offsets[condition]
            + phase_offsets[context.day_phase]
            + spec.offset_for(season)
        )
        band = temperature_band(ambient)
    kinds = tuple(
        hazard.kind
        for hazard in state.active_hazards
        if hazard.location_id == location_id and hazard.contains(context.tick)
    )
    _LOG.debug(
        "environment_observed season=%s band=%s hazard_count=%s",
        season.value,
        band.value if band is not None else "-",
        len(kinds),
    )
    return season, band, kinds


def _copy_observer_ids(values: Sequence[EntityId]) -> tuple[EntityId, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError("observer_ids must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("observer_ids must be an ordered sequence")
    copied = tuple(values)
    seen: set[EntityId] = set()
    for value in copied:
        if type(value) is not EntityId:
            raise TypeError("observer_ids entries must be EntityId")
        if value in seen:
            raise ValueError("observer_ids must not contain duplicates")
        seen.add(value)
    return copied


def _copy_prior_events(
    values: Sequence[WorldEvent], *, observation_tick: int
) -> tuple[WorldEvent, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError("prior_events must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("prior_events must be an ordered sequence")
    copied = tuple(values)
    seen: set[object] = set()
    for event in copied:
        if type(event) is not WorldEvent:
            raise TypeError("prior_events entries must be WorldEvent")
        require_replayable_event(event)
        if event.event_id in seen:
            raise ValueError("prior_events must not contain duplicate event_id")
        seen.add(event.event_id)
        if event.tick >= observation_tick:
            raise ValueError(
                "prior_events must come from a committed tick before observation"
            )
        if event.occurrence is None:
            raise ValueError("prior_events require occurrence context")
    return copied


def _sorted_locations(
    state: WorldState, location_id: EntityId
) -> tuple[ObservedLocation, ...]:
    location = state.locations.get(location_id)
    if location is None:
        return ()
    return (ObservedLocation(entity_id=location.entity_id, name=location.name),)


def _regional_context(
    state: WorldState, location_id: EntityId
) -> ObservedRegionalContext | None:
    spec = state.regions_migration
    if spec is None:
        return None
    region_by_id = {region.region_id: region for region in spec.regions}
    memberships = {row.location_id: row.region_id for row in spec.location_regions}
    region_id = memberships.get(location_id)
    region = None if region_id is None else region_by_id[region_id]
    return ObservedRegionalContext(
        region_id=region_id,
        label=None if region is None else region.label,
    )


def _observed_journey(
    state: WorldState, observer_id: EntityId, *, tick: int
) -> ObservedJourney | None:
    if state.journeys is None:
        return None
    for journey in state.journeys.values():
        if observer_id not in journey.participant_body_ids:
            continue
        phase = (
            ObservedJourneyPhase.PREPARATION
            if tick < journey.due_tick
            else ObservedJourneyPhase.ARRIVAL_PENDING
        )
        return ObservedJourney(
            origin_location_id=journey.origin_location_id,
            destination_location_id=journey.destination_location_id,
            origin_region_id=journey.origin_region_id,
            destination_region_id=journey.destination_region_id,
            start_tick=journey.start_tick,
            due_tick=journey.due_tick,
            arrival_wait_deadline_tick=journey.arrival_wait_deadline_tick,
            phase=phase,
            participant_count=len(journey.participant_body_ids),
        )
    return None


def _sorted_exits(
    state: WorldState, location_id: EntityId, *, physical_rules: object
) -> tuple[VisibleExit, ...]:
    location = state.locations.get(location_id)
    if location is None:
        return ()
    exits: list[VisibleExit] = []
    for destination_id in location.adjacent:
        destination = state.locations.get(destination_id)
        if destination is None:
            continue
        spec = state.regions_migration
        if spec is None:
            exits.append(
                VisibleExit(destination_id=destination_id, name=destination.name)
            )
            continue
        route = next(
            (
                candidate
                for candidate in spec.routes
                if candidate.edge_key
                == tuple(sorted((location_id.value, destination_id.value)))
            ),
            None,
        )
        from world.models import PhysicalRules, default_physical_rules

        rules = (
            physical_rules
            if type(physical_rules) is PhysicalRules
            else default_physical_rules()
        )
        memberships = {row.location_id: row.region_id for row in spec.location_regions}
        exits.append(
            VisibleExit(
                destination_id=destination_id,
                name=destination.name,
                travel_duration_ticks=1 if route is None else route.duration_ticks,
                fatigue_cost=(
                    rules.move_fatigue if route is None else route.fatigue_cost
                ),
                destination_region_id=memberships.get(destination_id),
            )
        )
    exits.sort(key=lambda value: value.destination_id.value)
    return tuple(exits)


def _sorted_items(
    state: WorldState,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    include_ground: bool,
    possession_succession_active: bool = False,
) -> tuple[ObservedItem, ...]:
    selected: list[ObservedItem] = []
    corpse_count = 0
    for item_id in sorted(state.items, key=lambda entity: entity.value):
        item = state.items[item_id]
        projected = _project_item(
            state,
            item,
            observer_id=observer_id,
            location_id=location_id,
            include_ground=include_ground,
            possession_succession_active=possession_succession_active,
        )
        if projected is not None:
            if projected.placement is ObservedItemPlacement.CORPSE_HERE:
                corpse_count += 1
            selected.append(projected)
    if corpse_count:
        _LOG.debug("corpse_item_projected item_count=%s", corpse_count)
    return tuple(selected)


def _project_item(
    state: WorldState,
    item: Item,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    include_ground: bool,
    possession_succession_active: bool = False,
) -> ObservedItem | None:
    if item.holder_id == observer_id:
        placement = ObservedItemPlacement.HELD_BY_SELF
    elif include_ground and item.location_id == location_id:
        placement = ObservedItemPlacement.GROUND_HERE
    elif (
        possession_succession_active
        and include_ground
        and item.entity_id in state.corpse_custody_item_ids
        and item.holder_id is not None
    ):
        holder = state.bodies.get(item.holder_id)
        if (
            holder is None
            or holder.life_status is not LifeStatus.DEAD
            or holder.location_id != location_id
        ):
            return None
        placement = ObservedItemPlacement.CORPSE_HERE
    else:
        return None
    return ObservedItem(
        entity_id=item.entity_id,
        name=item.name,
        kind=item.kind,
        load=item.load,
        placement=placement,
    )


def _sorted_resources(
    state: WorldState, location_id: EntityId
) -> tuple[ObservedResource, ...]:
    selected: list[ObservedResource] = []
    for resource_id in sorted(state.resources, key=lambda entity: entity.value):
        resource = state.resources[resource_id]
        if resource.location_id != location_id:
            continue
        selected.append(
            ObservedResource(
                entity_id=resource.entity_id,
                name=resource.name,
                kind=resource.kind,
                quantity=resource.quantity,
                unit=resource.unit,
            )
        )
    return tuple(selected)


def _sorted_structures(
    state: WorldState, location_id: EntityId
) -> tuple[ObservedStructure, ...]:
    selected: list[ObservedStructure] = []
    for structure_id in sorted(state.structures, key=lambda entity: entity.value):
        structure = state.structures[structure_id]
        if structure.location_id != location_id:
            continue
        selected.append(
            ObservedStructure(
                entity_id=structure.entity_id,
                location_id=structure.location_id,
                kind=structure.kind,
                integrity=structure.integrity,
                stored_quantity=structure.stored_quantity,
            )
        )
    return tuple(selected)


def _sorted_artifacts(
    state: WorldState,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    include_ground: bool,
    durable_perception_mode: str | None = None,
    include_custodian: bool = False,
) -> tuple[ObservedArtifact, ...]:
    selected: list[ObservedArtifact] = []
    for artifact_id in sorted(state.artifacts, key=lambda entity: entity.value):
        artifact = state.artifacts[artifact_id]
        projected = _project_artifact(
            artifact,
            observer_id=observer_id,
            location_id=location_id,
            include_ground=include_ground,
            durable_perception_mode=durable_perception_mode,
            include_custodian=include_custodian,
        )
        if projected is not None:
            selected.append(projected)
    return tuple(selected)


def _sorted_repositories(
    state: WorldState,
    *,
    location_id: EntityId,
    perception_mode: str,
) -> tuple[ObservedRepository, ...]:
    from world.repositories import RepositoryStatus

    selected: list[ObservedRepository] = []
    for repository_id in sorted(state.repositories, key=lambda entity: entity.value):
        repository = state.repositories[repository_id]
        if repository.location_id != location_id:
            continue
        if repository.status is RepositoryStatus.DESTROYED:
            continue
        if perception_mode == "container_only":
            selected.append(
                ObservedRepository(
                    repository_id=repository.repository_id,
                    location_id=repository.location_id,
                    status=repository.status.value,
                    member_count=len(repository.member_artifact_ids),
                )
            )
            continue
        selected.append(
            ObservedRepository(
                repository_id=repository.repository_id,
                location_id=repository.location_id,
                status=repository.status.value,
                member_count=len(repository.member_artifact_ids),
                access_mode=repository.access_mode.value,
                structure_id=repository.structure_id,
                founder_ids=repository.founder_ids,
                index_entry_count=len(repository.index_entries),
                last_maintained_tick=repository.last_maintained_tick,
                neglect_streak=repository.neglect_streak,
                index_entry_ids=tuple(
                    entry.entry_id for entry in repository.index_entries
                ),
            )
        )
    return tuple(selected)


def _project_artifact(
    artifact: InformationArtifact,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    include_ground: bool,
    durable_perception_mode: str | None = None,
    include_custodian: bool = False,
) -> ObservedArtifact | None:
    # Tombstones are inspection/analysis-only — never agent Observation.
    if artifact.integrity is RecordIntegrity.DESTROYED:
        return None
    if artifact.holder_id == observer_id:
        placement = ObservedItemPlacement.HELD_BY_SELF
    elif include_ground and artifact.location_id == location_id:
        placement = ObservedItemPlacement.GROUND_HERE
    else:
        return None
    genre = None
    parent_id = None
    source_id = None
    copy_generation = None
    integrity = None
    annotation_revisions = None
    lost_mark_count = None
    if durable_perception_mode is not None:
        genre = artifact.record_genre
        if durable_perception_mode == "marks_and_meta":
            parent_id = artifact.parent_artifact_id
            source_id = artifact.source_artifact_id
            copy_generation = artifact.copy_generation
            integrity = artifact.integrity
            annotation_revisions = artifact.annotation_revisions
            lost_mark_count = artifact.lost_mark_count
        _LOG.debug(
            "observed_artifact_projected integrity=%s copy_generation=%s",
            integrity.value if integrity is not None else "-",
            copy_generation if copy_generation is not None else "-",
        )
    custodian = artifact.custodian_repository_id if include_custodian else None
    return ObservedArtifact(
        entity_id=artifact.artifact_id,
        kind=artifact.kind,
        author_id=artifact.author_id,
        created_tick=artifact.created_tick,
        content=artifact.content,
        content_revision=artifact.content_revision,
        placement=placement,
        record_genre=genre,
        parent_artifact_id=parent_id,
        source_artifact_id=source_id,
        copy_generation=copy_generation,
        integrity=integrity,
        annotation_revisions=annotation_revisions,
        lost_mark_count=lost_mark_count,
        custodian_repository_id=custodian,
    )


def _sorted_visible_bodies(
    state: WorldState,
    location_id: EntityId,
    observer_id: EntityId,
    *,
    context: ObservationContext,
) -> tuple[VisibleBody, ...]:
    selected: list[VisibleBody] = []
    for body_id in sorted(state.bodies, key=lambda entity: entity.value):
        if body_id == observer_id:
            continue
        body = state.bodies[body_id]
        if body.location_id != location_id:
            continue
        selected.append(
            VisibleBody(
                entity_id=body_id,
                life_status=body.life_status,
                coarse_health=coarse_health_for(body),
                lifecycle=_lifecycle_for(context, body_id),
                kinship_visible=_kinship_other_for(
                    context, observer_id=observer_id, other_body_id=body_id
                ),
                dependency_needs=_dependency_needs_for(context, body_id),
            )
        )
    return tuple(selected)


def _lifecycle_for(
    context: ObservationContext, body_id: EntityId
) -> ObservedLifecycle | None:
    views = context.lifecycle_by_body
    if views is None:
        return None
    return views.get(body_id)


def _dependency_needs_for(
    context: ObservationContext, body_id: EntityId
) -> ObservedDependencyNeeds | None:
    views = context.dependency_needs_by_body
    if views is None:
        return None
    # Only expose need summaries for bodies that already have lifecycle facts.
    if _lifecycle_for(context, body_id) is None:
        return None
    return views.get(body_id)


def _kinship_self_for(
    context: ObservationContext, body_id: EntityId
) -> ObservedKinshipVisible | None:
    views = context.kinship_self_by_body
    if views is None:
        return None
    return views.get(body_id)


def _kinship_other_for(
    context: ObservationContext,
    *,
    observer_id: EntityId,
    other_body_id: EntityId,
) -> ObservedKinshipVisible | None:
    """Expose only self-incident kin facts about a visible other body."""
    from world.observations import ObservedKinshipVisible

    self_view = _kinship_self_for(context, observer_id)
    if type(self_view) is not ObservedKinshipVisible:
        return None
    agents = context.kinship_agent_by_body
    if agents is None:
        return None
    other_agent = agents.get(other_body_id)
    if other_agent is None:
        return None
    if other_agent in self_view.parents:
        return ObservedKinshipVisible(parents=(other_agent,), children=())
    if other_agent in self_view.children:
        return ObservedKinshipVisible(parents=(), children=(other_agent,))
    return None


def _project_event_window(
    *,
    observer_id: EntityId,
    location_id: EntityId,
    content_visible: bool,
    prior_events: tuple[WorldEvent, ...],
    state: WorldState | None = None,
    structured_commitments_active: bool = False,
    subjective_valuation_active: bool = False,
    collective_projects_active: bool = False,
    public_goods_active: bool = False,
) -> tuple[tuple[ObservedOccurrence, ...], tuple[ObservedCommunication, ...]]:
    occurrences: list[ObservedOccurrence] = []
    communications: list[ObservedCommunication] = []
    for event in prior_events:
        if not subjective_valuation_active and type(event.details) in {
            ExchangeProposed,
            ExchangeWithdrawn,
            ExchangeCompleted,
        }:
            continue
        if not collective_projects_active and type(event.details) in {
            ProjectCreated,
            ProjectContributed,
            ProjectShortage,
            ProjectAbandoned,
            ProjectCompleted,
            PublicGoodBenefit,
            PublicGoodMaintained,
            PublicGoodOpposed,
        }:
            continue
        if not public_goods_active and type(event.details) in {
            PublicGoodBenefit,
            PublicGoodMaintained,
            PublicGoodOpposed,
        }:
            continue
        occurrence = event.occurrence
        assert occurrence is not None
        if _is_communication(event):
            communication = _project_communication(event, observer_id=observer_id)
            if communication is not None:
                communications.append(communication)
            continue
        role = _audience_role(
            event,
            observer_id=observer_id,
            location_id=location_id,
            content_visible=content_visible,
        )
        if role is None:
            continue
        if type(event.details) is ExperimentResolved:
            viewer = "actor" if role is ObservationAudienceRole.ACTOR else "bystander"
            _LOG.debug(
                "experiment_occurrence_projected viewer_role=%s outcome_class=%s",
                viewer,
                event.details.outcome_class,
            )
        occurrences.append(
            ObservedOccurrence(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.OCCURRENCE,
                    source_tick=event.tick,
                    source_event_id=event.event_id,
                ),
                kind=event.event_type,
                audience_role=role,
                actor_id=event.actor_id,
                other_entity_id=_other_entity_for_role(event, role),
                destination_id=occurrence.destination_location_id,
                success=_success_fact(event),
                public_facts=_public_facts_for_role(
                    event,
                    role,
                    state=state,
                    structured_commitments_active=structured_commitments_active,
                    subjective_valuation_active=subjective_valuation_active,
                    collective_projects_active=collective_projects_active,
                    public_goods_active=public_goods_active,
                ),
            )
        )
    return tuple(occurrences), tuple(communications)


def _is_communication(event: WorldEvent) -> bool:
    return isinstance(event.details, (Talked, Asked, Told))


def _project_communication(
    event: WorldEvent, *, observer_id: EntityId
) -> ObservedCommunication | None:
    occurrence = event.occurrence
    assert occurrence is not None
    details = event.details
    assert isinstance(details, (Talked, Asked, Told))
    speaker_id = event.actor_id
    if speaker_id is None:
        return None
    listener_id = details.recipient_id
    if observer_id not in {speaker_id, listener_id} and observer_id not in set(
        occurrence.private_recipient_ids
    ):
        return None
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=event.tick,
            source_event_id=event.event_id,
        ),
        speaker_id=speaker_id,
        listener_id=listener_id,
        utterance=details.utterance,
        action_kind=details.kind,
    )


def _audience_role(
    event: WorldEvent,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    content_visible: bool,
) -> ObservationAudienceRole | None:
    occurrence = event.occurrence
    assert occurrence is not None
    if event.actor_id == observer_id:
        return ObservationAudienceRole.ACTOR
    producer = _production_actor(event)
    if producer is not None and producer == observer_id:
        return ObservationAudienceRole.ACTOR
    if event.target_id == observer_id or observer_id in set(
        occurrence.affected_entity_ids
    ):
        return ObservationAudienceRole.TARGET
    origin = occurrence.origin_location_id
    destination = occurrence.destination_location_id
    at_origin = origin is not None and location_id == origin
    at_destination = destination is not None and location_id == destination
    if not (at_origin or at_destination):
        return None
    # Movement witnesses can observe leave/arrive at the edge even in darkness.
    if destination is not None and (at_origin or at_destination):
        return ObservationAudienceRole.WITNESS
    if not content_visible:
        return None
    return ObservationAudienceRole.BYSTANDER


def _other_entity_for_role(
    event: WorldEvent, role: ObservationAudienceRole
) -> EntityId | None:
    if type(event.details) is CommitmentDeclared:
        return event.target_id
    if role in {
        ObservationAudienceRole.BYSTANDER,
        ObservationAudienceRole.WITNESS,
    }:
        return event.target_id if role is ObservationAudienceRole.WITNESS else None
    return event.target_id


def _success_fact(event: WorldEvent) -> bool | None:
    details = event.details
    if type(details) is ExperimentResolved:
        if details.outcome_class in {"success", "partial_success"}:
            return True
        if details.outcome_class in {"failure", "harm"}:
            return False
        return None
    success = getattr(details, "success", None)
    if type(success) is bool:
        return success
    hit = getattr(details, "hit", None)
    if type(hit) is bool:
        return hit
    return None


def _public_facts_for_role(
    event: WorldEvent,
    role: ObservationAudienceRole,
    *,
    state: WorldState | None = None,
    structured_commitments_active: bool = False,
    subjective_valuation_active: bool = False,
    collective_projects_active: bool = False,
    public_goods_active: bool = False,
) -> dict[str, object]:
    if type(event.details) in {JourneyStarted, JourneyArrived, JourneyEnded}:
        if role not in {
            ObservationAudienceRole.ACTOR,
            ObservationAudienceRole.TARGET,
        }:
            return {"kind": event.event_type}
        if type(event.details) is JourneyStarted:
            journey = event.details.journey
            return {
                "kind": event.event_type,
                "journey_command_kind": event.details.command_kind,
                "journey_destination_id": journey.destination_location_id.value,
                "journey_due_tick": journey.due_tick,
                "journey_id": journey.journey_id,
            }
        if type(event.details) is JourneyArrived:
            return {
                "kind": event.event_type,
                "journey_destination_id": event.details.destination_location_id.value,
                "journey_id": event.details.journey_id,
                "journey_status": "arrived",
            }
        assert isinstance(event.details, JourneyEnded)
        return {
            "kind": event.event_type,
            "journey_id": event.details.journey_id,
            "journey_reason": event.details.reason,
            "journey_status": "ended",
        }
    experiment_facts = _experiment_public_facts(event, role)
    if experiment_facts is not None:
        return experiment_facts
    artifact_facts = _artifact_public_facts(event)
    if artifact_facts is not None:
        # Artifact occurrences expose only identity/revision — never marks.
        return {"kind": event.event_type, **artifact_facts}
    project_facts = _project_public_facts(
        event,
        state,
        active=collective_projects_active,
        public_goods_active=public_goods_active,
    )
    if project_facts is not None:
        return project_facts
    exchange_facts = _exchange_public_facts(
        event, state, active=subjective_valuation_active, role=role
    )
    if exchange_facts is not None:
        return exchange_facts
    facts: dict[str, object] = {"kind": event.event_type}
    possession_facts = _possession_public_facts(event)
    if possession_facts is not None:
        facts.update(possession_facts)
        _LOG.debug(
            "possession_occurrence kind=%s item_count=%s",
            event.details.kind,
            len(cast(Sequence[str], possession_facts["item_ids"])),
        )
    commitment_facts = _commitment_public_facts(event)
    if commitment_facts is not None:
        facts.update(commitment_facts)
        _LOG.debug(
            "commitment_occurrence kind=%s act=%s role=%s",
            commitment_facts["kind"],
            commitment_facts["act"],
            role.value,
        )
        return facts
    recipe_id = _production_recipe_id(event)
    if role is ObservationAudienceRole.BYSTANDER:
        if recipe_id is not None:
            facts["recipe_id"] = recipe_id
        return facts
    if event.actor_id is not None:
        facts["actor_id"] = event.actor_id.value
    if event.target_id is not None:
        facts["target_id"] = event.target_id.value
    if recipe_id is not None and role is ObservationAudienceRole.ACTOR:
        facts["recipe_id"] = recipe_id
    if structured_commitments_active and type(event.details) is Given:
        facts.update(_given_item_facts(event, state))
        _LOG.debug(
            "commitment_give_facts item_kind=%s",
            facts["item_kind"],
        )
    return facts


def _sorted_collective_projects(
    state: WorldState, location_id: EntityId, *, public_goods_active: bool = False
) -> tuple[ObservedCollectiveProject, ...]:
    selected: list[ObservedCollectiveProject] = []
    projects = sorted(
        state.collective_projects.values(),
        key=lambda item: item.project_id.value,
    )
    for project in projects:
        if project.location_id != location_id:
            continue
        selected.append(
            ObservedCollectiveProject(
                project_id=project.project_id,
                location_id=project.location_id,
                kind=project.kind.value,
                status=project.status.value,
                labor_done=project.labor_done,
                materials_done=project.materials_done,
                contributions=tuple(
                    ObservedProjectContribution(
                        actor_id=row.actor_id,
                        tick=row.tick,
                        accepted=row.accepted,
                        labor_delta=row.labor_delta,
                        item_id=row.item_id,
                    )
                    for row in project.contributions
                ),
                public_acts=project.public_acts if public_goods_active else (),
                linked_structure_id=(
                    project.linked_structure_id if public_goods_active else None
                ),
            )
        )
    return tuple(selected)


def _project_public_facts(
    event: WorldEvent,
    state: WorldState | None,
    *,
    active: bool,
    public_goods_active: bool = False,
) -> dict[str, object] | None:
    if not active:
        return None
    details = event.details
    if type(details) not in {
        ProjectCreated,
        ProjectContributed,
        ProjectShortage,
        ProjectAbandoned,
        ProjectCompleted,
        PublicGoodBenefit,
        PublicGoodMaintained,
        PublicGoodOpposed,
    }:
        return None
    if type(details) in {PublicGoodBenefit, PublicGoodMaintained, PublicGoodOpposed}:
        assert isinstance(
            details, (PublicGoodBenefit, PublicGoodMaintained, PublicGoodOpposed)
        )
        if not public_goods_active:
            return None
        project = (
            None if state is None else state.collective_projects.get(details.project_id)
        )
        facts: dict[str, object] = {
            "project_id": details.project_id.value,
            "kind": (
                details.project_kind
                if type(details) is PublicGoodBenefit
                else None
                if project is None
                else project.kind.value
            ),
        }
        if type(details) is PublicGoodBenefit:
            facts["benefit_code"] = details.benefit_code
            facts["source"] = details.source
            if details.resulting_hunger is not None:
                facts["resulting_hunger"] = details.resulting_hunger
            if details.resulting_thirst is not None:
                facts["resulting_thirst"] = details.resulting_thirst
        elif type(details) is PublicGoodMaintained:
            facts["accepted"] = details.accepted
        else:
            assert isinstance(details, PublicGoodOpposed)
            facts["status"] = details.status
        _LOG.debug(
            "public_good_occurrence_projected kind=%s project_id=%s",
            details.kind,
            details.project_id.value,
        )
        return facts
    assert isinstance(
        details,
        (
            ProjectCreated,
            ProjectContributed,
            ProjectShortage,
            ProjectAbandoned,
            ProjectCompleted,
        ),
    )
    project = None
    if state is not None:
        project = state.collective_projects.get(details.project_id)
    kind = getattr(details, "project_kind", None)
    if kind is None and project is not None:
        kind = project.kind.value
    labor_done = getattr(details, "labor_done", None)
    if labor_done is None and project is not None:
        labor_done = project.labor_done
    materials_done = getattr(details, "materials_done", None)
    if materials_done is None and project is not None:
        materials_done = project.materials_done
    if type(details) is ProjectCreated:
        status = "open"
        labor_done = 0
        materials_done = 0
    elif type(details) is ProjectAbandoned:
        status = "abandoned"
    elif type(details) is ProjectCompleted:
        status = "completed"
    elif project is not None:
        status = project.status.value
    else:
        status = "open"
    payload = {
        "project_id": details.project_id.value,
        "kind": kind,
        "labor_done": labor_done,
        "materials_done": materials_done,
        "status": status,
    }
    if public_goods_active and type(details) is ProjectContributed:
        from world.collective_projects import PUBLIC_GOOD_KINDS

        payload["accepted"] = details.accepted
        payload["public_good"] = (
            project is not None and project.kind in PUBLIC_GOOD_KINDS
        )
    return payload


def _commitment_public_facts(event: WorldEvent) -> dict[str, object] | None:
    details = event.details
    if type(details) is not CommitmentDeclared:
        return None
    return {
        "kind": details.commitment_kind,
        "act": details.act,
        "owed_by": details.owed_by,
        "item_kind": details.item_kind,
        "service": details.service,
        "quantity": details.quantity,
        "due_kind": details.due_kind,
        "due_tick": details.due_tick,
        "now_item_kind": details.now_item_kind,
    }


def _exchange_public_facts(
    event: WorldEvent,
    state: WorldState | None,
    *,
    active: bool,
    role: ObservationAudienceRole,
) -> dict[str, object] | None:
    details = event.details
    if type(details) not in {ExchangeProposed, ExchangeWithdrawn, ExchangeCompleted}:
        return None
    assert isinstance(details, (ExchangeProposed, ExchangeWithdrawn, ExchangeCompleted))
    if not active:
        return None
    give_ids = tuple(item.value for item in details.give_item_ids)
    take_ids = tuple(item.value for item in details.take_item_ids)
    if type(details) is ExchangeCompleted:
        give_kinds = details.give_item_kinds
        take_kinds = details.take_item_kinds
    else:
        give_kinds = tuple(
            _visible_item_kind(state, item) for item in details.give_item_ids
        )
        take_kinds = tuple(
            _visible_item_kind(state, item) for item in details.take_item_ids
        )
    _LOG.debug(
        "exchange_occurrence act=%s role=%s give_len=%s take_len=%s",
        details.act,
        role.value,
        len(give_ids),
        len(take_ids),
    )
    return {
        "kind": details.kind,
        "act": details.act,
        "give_item_ids": give_ids,
        "take_item_ids": take_ids,
        "give_item_kinds": give_kinds,
        "take_item_kinds": take_kinds,
    }


def _visible_item_kind(state: WorldState | None, item_id: EntityId) -> str:
    if state is None:
        return ""
    item = state.items.get(item_id)
    if item is None:
        return ""
    return item.kind.value


def _exchange_visible_holdings(
    state: WorldState, observer_id: EntityId, location_id: EntityId
) -> tuple[ExchangeVisibleHolding, ...]:
    rows: list[ExchangeVisibleHolding] = []
    for body in state.bodies.values():
        if body.entity_id == observer_id or body.location_id != location_id:
            continue
        for item_id in body.inventory:
            item = state.items.get(item_id)
            if item is None or item.holder_id != body.entity_id:
                continue
            rows.append(
                ExchangeVisibleHolding(
                    body_id=body.entity_id,
                    item_id=item.entity_id,
                    kind=item.kind,
                    load=item.load,
                )
            )
    rows.sort(key=lambda row: (row.body_id.value, row.item_id.value))
    _LOG.debug("exchange_holdings_visible holding_count=%s", len(rows))
    return tuple(rows)


def _given_item_facts(event: WorldEvent, state: WorldState | None) -> dict[str, object]:
    details = event.details
    assert type(details) is Given
    item = None if state is None else state.items.get(details.item_id)
    item_kind = "unspecified" if item is None else item.kind.value
    return {"item_id": details.item_id.value, "item_kind": item_kind}


def _possession_public_facts(event: WorldEvent) -> dict[str, object] | None:
    details = event.details
    if type(details) is CorpseCustodyOpened:
        return {
            "decedent_id": details.body_id.value,
            "item_ids": [item.value for item in details.item_ids],
        }
    if type(details) is TakenFromCorpse:
        return {
            "decedent_id": details.source_body_id.value,
            "item_ids": [details.item_id.value],
        }
    if type(details) is PossessionClaimAsserted:
        item_ids = [] if details.item_id is None else [details.item_id.value]
        return {
            "decedent_id": details.decedent_id.value,
            "doctrine": details.doctrine,
            "item_ids": item_ids,
        }
    return None


def _experiment_public_facts(
    event: WorldEvent, role: ObservationAudienceRole
) -> dict[str, object] | None:
    details = event.details
    if type(details) is not ExperimentResolved:
        return None
    facts: dict[str, object] = {
        "kind": event.event_type,
        "outcome_class": details.outcome_class,
        "delta": details.delta,
    }
    if role is ObservationAudienceRole.ACTOR:
        facts["operator"] = details.operator
        facts["discovery_mode"] = details.discovery_mode
    return facts


def _artifact_public_facts(event: WorldEvent) -> dict[str, object] | None:
    details = event.details
    if type(details) not in _ARTIFACT_DETAIL_TYPES:
        return None
    if type(details) is ArtifactCopied:
        facts: dict[str, object] = {
            "artifact_id": details.child_artifact_id.value,
            "content_revision": details.content_revision,
            "record_genre": details.record_genre,
            "integrity": "intact",
        }
        return facts
    if type(details) in {
        ArtifactAnnotated,
        ArtifactDamaged,
        ArtifactPartiallyLost,
    }:
        integrity = getattr(details, "integrity", None)
        if integrity is None:
            integrity = getattr(details, "next_integrity", None)
        return {
            "artifact_id": details.artifact_id.value,  # type: ignore[union-attr]
            "content_revision": details.content_revision,  # type: ignore[union-attr]
            "integrity": integrity,
        }
    facts = {
        "artifact_id": details.artifact_id.value,  # type: ignore[union-attr]
        "artifact_kind": details.artifact_kind.value,  # type: ignore[union-attr]
        "content_revision": details.content_revision,  # type: ignore[union-attr]
    }
    if type(details) is ArtifactDestroyed and (
        details.tombstone or details.integrity is not None
    ):
        facts["integrity"] = (
            details.integrity if details.integrity is not None else "destroyed"
        )
        facts["record_genre"] = None
    return facts


def _production_recipe_id(event: WorldEvent) -> str | None:
    details = event.details
    if type(details) not in _PRODUCTION_DETAIL_TYPES:
        return None
    return details.recipe_id.value  # type: ignore[union-attr]


def _production_actor(event: WorldEvent) -> EntityId | None:
    details = event.details
    if type(details) is ItemCrafted:
        return details.resulting_holder_id
    if type(details) in _PRODUCTION_DETAIL_TYPES:
        return event.actor_id
    return None
