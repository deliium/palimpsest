"""Public immutable world bootstrap and agent registration boundary.

Bootstrap values validate at construction and never expose private ``World`` /
``WorldState`` in public annotations. Engine materialization stays internal.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from agents.models import AgentId
from simulation.registrations import AgentRegistration as AgentRegistration
from world._disease import DiseaseConditionRow
from world._ecological_resources import EcologicalStockRow
from world.artifacts import InformationArtifact
from world.identifiers import EntityId, WorldId, WorldRevision
from world.measurement import InstrumentState, MeasurementReference
from world.models import AgentBody, Item, Location, Resource, Weather
from world.regions import Journey, RegionsMigrationSpec
from world.repositories import KnowledgeRepository

if TYPE_CHECKING:
    from world._state import World

__all__ = [
    "AgentRegistration",
    "RegistrationTranslator",
    "WorldBootstrap",
    "build_initial_ecological_resources",
    "disease_bootstrap_state",
    "registration_translator",
]

_LOGGER = logging.getLogger("simulation.bootstrap")
_ARTIFACT_ID_COLLISION = "artifact_id_collision"


@dataclass(frozen=True, slots=True)
class RegistrationTranslator:
    """Deterministic IdentityTranslator derived from ordered registrations."""

    _forward: Mapping[AgentId, EntityId]
    _reverse: Mapping[EntityId, AgentId]
    _order: tuple[AgentRegistration, ...]

    def to_entity_id(self, agent_id: AgentId) -> EntityId:
        if type(agent_id) is not AgentId:
            raise TypeError("to_entity_id requires AgentId")
        try:
            return self._forward[agent_id]
        except KeyError as exc:
            raise KeyError(f"unknown agent_id {agent_id.value!r}") from exc

    def to_agent_id(self, entity_id: EntityId) -> AgentId:
        if type(entity_id) is not EntityId:
            raise TypeError("to_agent_id requires EntityId")
        try:
            return self._reverse[entity_id]
        except KeyError as exc:
            raise KeyError(f"unknown entity_id {entity_id.value!r}") from exc

    @property
    def ordered_registrations(self) -> tuple[AgentRegistration, ...]:
        return self._order


@dataclass(frozen=True, slots=True)
class WorldBootstrap:
    """Public factory input for WorldEngine. Contains no private authority types.

    Dead bodies may be registered for observation/history but cannot act once
    the engine enforces life status. Registration order is canonical for later
    observation and admission sequencing.
    """

    world_id: WorldId
    revision: WorldRevision
    locations: Sequence[Location] = field(default_factory=tuple)
    items: Sequence[Item] = field(default_factory=tuple)
    resources: Sequence[Resource] = field(default_factory=tuple)
    bodies: Sequence[AgentBody] = field(default_factory=tuple)
    weather: Sequence[Weather] = field(default_factory=tuple)
    registrations: Sequence[AgentRegistration] = field(default_factory=tuple)
    artifacts: Sequence[InformationArtifact] = field(default_factory=tuple)
    repositories: Sequence[KnowledgeRepository] = field(default_factory=tuple)
    instrument_states: Sequence[InstrumentState] = field(default_factory=tuple)
    measurement_references: Sequence[MeasurementReference] = field(
        default_factory=tuple
    )
    regions_migration: RegionsMigrationSpec | None = None
    journeys: Sequence[Journey] | None = None
    disease_state: Mapping[EntityId, DiseaseConditionRow] | None = None
    ecological_resources: Mapping[EntityId, EcologicalStockRow] | None = None
    ecological_policy_digest: str | None = None

    def __post_init__(self) -> None:
        if type(self.world_id) is not WorldId:
            raise TypeError("WorldBootstrap.world_id must be WorldId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("WorldBootstrap.revision must be WorldRevision")
        locations = _copy_models(
            "WorldBootstrap.locations", self.locations, model_type=Location
        )
        items = _copy_models("WorldBootstrap.items", self.items, model_type=Item)
        resources = _copy_models(
            "WorldBootstrap.resources", self.resources, model_type=Resource
        )
        bodies = _copy_models(
            "WorldBootstrap.bodies", self.bodies, model_type=AgentBody
        )
        weather = _copy_models(
            "WorldBootstrap.weather", self.weather, model_type=Weather
        )
        registrations = _copy_registrations(
            "WorldBootstrap.registrations", self.registrations
        )
        artifacts = _copy_models(
            "WorldBootstrap.artifacts",
            self.artifacts,
            model_type=InformationArtifact,
        )
        repositories = _copy_models(
            "WorldBootstrap.repositories",
            self.repositories,
            model_type=KnowledgeRepository,
        )
        instrument_states = _copy_models(
            "WorldBootstrap.instrument_states",
            self.instrument_states,
            model_type=InstrumentState,
        )
        measurement_references = _copy_models(
            "WorldBootstrap.measurement_references",
            self.measurement_references,
            model_type=MeasurementReference,
        )
        if (
            self.regions_migration is not None
            and type(self.regions_migration) is not RegionsMigrationSpec
        ):
            raise TypeError(
                "WorldBootstrap.regions_migration must be RegionsMigrationSpec"
            )
        journeys = (
            None
            if self.journeys is None and self.regions_migration is None
            else _copy_models(
                "WorldBootstrap.journeys",
                () if self.journeys is None else self.journeys,
                model_type=Journey,
            )
        )
        if journeys and self.regions_migration is None:
            raise ValueError(
                "journeys require regions_migration (code=journey_channel_off)"
            )
        object.__setattr__(self, "locations", locations)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "bodies", bodies)
        object.__setattr__(self, "weather", weather)
        object.__setattr__(self, "registrations", registrations)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "repositories", repositories)
        object.__setattr__(self, "instrument_states", instrument_states)
        object.__setattr__(
            self, "measurement_references", measurement_references
        )
        object.__setattr__(self, "journeys", journeys)
        if self.disease_state is not None and not isinstance(
            self.disease_state, Mapping
        ):
            raise TypeError("WorldBootstrap.disease_state must be a mapping or None")
        object.__setattr__(
            self,
            "disease_state",
            None
            if self.disease_state is None
            else MappingProxyType(self.disease_state),
        )
        if self.ecological_resources is not None and not isinstance(
            self.ecological_resources, Mapping
        ):
            raise TypeError(
                "WorldBootstrap.ecological_resources must be a mapping or None"
            )
        if self.ecological_resources is None:
            if self.ecological_policy_digest is not None:
                raise ValueError(
                    "ecological_policy_digest requires ecological_resources "
                    "(code=ecological_digest_without_state)"
                )
            object.__setattr__(self, "ecological_resources", None)
            object.__setattr__(self, "ecological_policy_digest", None)
        else:
            if type(self.ecological_policy_digest) is not str:
                raise TypeError(
                    "ecological_policy_digest must be str when ecology is active"
                )
            object.__setattr__(
                self,
                "ecological_resources",
                MappingProxyType(self.ecological_resources),
            )
            object.__setattr__(
                self,
                "ecological_policy_digest",
                self.ecological_policy_digest,
            )
        _validate_registrations_against_models(
            locations=locations,
            items=items,
            resources=resources,
            bodies=bodies,
            registrations=registrations,
            artifacts=artifacts,
        )
        # Reuse authoritative graph validation without exposing WorldState.
        from world._state import WorldState

        try:
            WorldState(
                self.revision,
                locations=locations,
                items=items,
                resources=resources,
                bodies=bodies,
                weather=weather,
                artifacts=artifacts,
                repositories=repositories,
                instrument_states=instrument_states,
                measurement_references=measurement_references,
                regions_migration=self.regions_migration,
                journeys=journeys,
                disease_state=self.disease_state,
                ecological_resources=self.ecological_resources,
                ecological_policy_digest=self.ecological_policy_digest,
            )
        except ValueError as exc:
            message = str(exc)
            if (
                "duplicate physical EntityId" in message
                or "duplicate artifact entity_id" in message
            ):
                _LOGGER.error(
                    "artifact_seed_failed reason_code=%s detail=%s",
                    _ARTIFACT_ID_COLLISION,
                    message,
                )
            raise
        translator = registration_translator(self)
        for registration in registrations:
            entity_id = translator.to_entity_id(registration.agent_id)
            if entity_id != registration.entity_id:
                raise ValueError("registration translator forward mismatch")
            if translator.to_agent_id(entity_id) != registration.agent_id:
                raise ValueError("registration translator round-trip mismatch")
        _LOGGER.debug(
            "artifacts_seeded count=%s",
            len(artifacts),
        )
        _LOGGER.debug(
            "world_bootstrap_validated world_id=%s revision=%s "
            "location_count=%s item_count=%s resource_count=%s body_count=%s "
            "weather_count=%s registration_count=%s artifact_count=%s "
            "region_count=%s journey_count=%s instrument_count=%s "
            "reference_count=%s",
            self.world_id.value,
            self.revision.value,
            len(locations),
            len(items),
            len(resources),
            len(bodies),
            len(weather),
            len(registrations),
            len(artifacts),
            (
                0
                if self.regions_migration is None
                else len(self.regions_migration.regions)
            ),
            0 if journeys is None else len(journeys),
            len(instrument_states),
            len(measurement_references),
        )

    def validate_finalized_boundary(self, completed_tick: int) -> None:
        """Validate pending journey liveness at a durable tick boundary."""
        if type(completed_tick) is not int or completed_tick < 0:
            raise ValueError("completed_tick must be non-negative")
        state = _materialize_world(self).state
        state.validate_finalized_boundary(completed_tick)


def registration_translator(bootstrap: WorldBootstrap) -> RegistrationTranslator:
    """Build a deterministic translator from a validated bootstrap."""
    if type(bootstrap) is not WorldBootstrap:
        raise TypeError("registration_translator requires WorldBootstrap")
    return _translator_from_registrations(bootstrap.registrations)


def _materialize_world(bootstrap: WorldBootstrap) -> World:
    """Internal: construct private World authority from a validated bootstrap.

    Copies seeded ``InformationArtifact`` rows into ``WorldState.artifacts``.
    Does not create subjective interpretation ledgers.
    """
    from world._state import World, WorldState

    if type(bootstrap) is not WorldBootstrap:
        raise TypeError("_materialize_world requires WorldBootstrap")
    try:
        state = WorldState(
            bootstrap.revision,
            locations=bootstrap.locations,
            items=bootstrap.items,
            resources=bootstrap.resources,
            bodies=bootstrap.bodies,
            weather=bootstrap.weather,
            artifacts=bootstrap.artifacts,
            repositories=bootstrap.repositories,
            instrument_states=bootstrap.instrument_states,
            measurement_references=bootstrap.measurement_references,
            regions_migration=bootstrap.regions_migration,
            journeys=bootstrap.journeys,
            disease_state=bootstrap.disease_state,
            ecological_resources=bootstrap.ecological_resources,
            ecological_policy_digest=bootstrap.ecological_policy_digest,
        )
    except ValueError as exc:
        message = str(exc)
        if (
            "duplicate physical EntityId" in message
            or "duplicate artifact entity_id" in message
        ):
            _LOGGER.error(
                "artifact_seed_failed reason_code=%s detail=%s",
                _ARTIFACT_ID_COLLISION,
                message,
            )
        raise
    _LOGGER.debug("artifacts_seeded count=%s", len(bootstrap.artifacts))
    _LOGGER.debug(
        "disease_seeded channel=%s row_count=%s",
        "on" if bootstrap.disease_state is not None else "off",
        0 if bootstrap.disease_state is None else len(bootstrap.disease_state),
    )
    _LOGGER.debug(
        "ecological_seeded channel=%s row_count=%s",
        "on" if bootstrap.ecological_resources is not None else "off",
        0
        if bootstrap.ecological_resources is None
        else len(bootstrap.ecological_resources),
    )
    return World(bootstrap.world_id, state)


def build_initial_ecological_resources(
    config: object,
) -> tuple[Mapping[EntityId, EcologicalStockRow], str] | None:
    """Build zero-damage ecology rows and policy digest from runner config."""
    spec = getattr(config, "ecological_resources", None)
    if spec is None:
        return None
    from simulation.ecological_resources_config import (
        EcologicalResourcesSpec,
        policy_sha256_for_ecological_resources,
    )
    from world._ecological_resources import (
        bootstrap_ecological_rows,
        validate_ecological_resources_state,
    )

    if type(spec) is not EcologicalResourcesSpec:
        raise TypeError("ecological_resources must be EcologicalResourcesSpec")
    scenario = getattr(config, "scenario", None)
    if scenario is None:
        raise TypeError("build_initial_ecological_resources requires a scenario")
    rows = bootstrap_ecological_rows(
        nodes=tuple(
            (node.resource_id, node.minimum_capacity_tenths) for node in spec.nodes
        )
    )
    digest = policy_sha256_for_ecological_resources(spec)
    resources = {resource.entity_id: resource for resource in scenario.resources}
    validate_ecological_resources_state(
        rows,
        resources=resources,
        policy_digest=digest,
        expected_digest=digest,
        expected_floors={
            node.resource_id: node.minimum_capacity_tenths for node in spec.nodes
        },
    )
    _LOGGER.debug(
        "ecological_bootstrap_ready managed_count=%s",
        len(rows),
    )
    return rows, digest


def disease_bootstrap_state(
    config: object,
) -> Mapping[EntityId, DiseaseConditionRow] | None:
    """Internal: build founder latent rows for one enabled disease channel."""
    spec = getattr(config, "disease_mechanics", None)
    if spec is None:
        return None
    from world._disease import bootstrap_disease_rows

    scenario = getattr(config, "scenario", None)
    if scenario is None:
        raise TypeError("disease_bootstrap_state requires a scenario")
    body_index = {body.entity_id: body for body in scenario.bodies}
    return bootstrap_disease_rows(
        founder_ids=spec.initial_latent_entity_ids,
        latent_ticks=spec.latent_ticks,
        tick0=0,
        body_index=body_index,
    )


def _disease_state_from_snapshot(
    snapshot: object,
) -> Mapping[EntityId, DiseaseConditionRow] | None:
    """Rebuild private disease rows from the v22 checkpoint section."""
    from simulation.disease_checkpoint import DiseaseCheckpointSection
    from world._disease import DiseaseConditionRow, DiseasePhase

    section = getattr(snapshot, "disease_mechanics", None)
    if section is None:
        return None
    if type(section) is not DiseaseCheckpointSection:
        raise TypeError("snapshot.disease_mechanics must be DiseaseCheckpointSection")
    return {
        row.body_id: DiseaseConditionRow(
            phase=DiseasePhase(row.phase),
            due_tick=row.due_tick,
            symptomatic=row.symptomatic,
        )
        for row in section.rows
    }


def _bootstrap_from_snapshot(snapshot: object) -> WorldBootstrap:
    """Internal: derive a WorldBootstrap view from an immutable checkpoint."""
    from simulation.persistence import WorldSnapshot

    if type(snapshot) is not WorldSnapshot:
        raise TypeError("_bootstrap_from_snapshot requires WorldSnapshot")
    return WorldBootstrap(
        world_id=snapshot.world_id,
        revision=snapshot.revision,
        locations=snapshot.locations,
        items=snapshot.items,
        resources=snapshot.resources,
        bodies=snapshot.bodies,
        weather=snapshot.weather,
        registrations=snapshot.registrations,
        artifacts=snapshot.artifacts,
        repositories=snapshot.repositories,
        instrument_states=getattr(snapshot, "instrument_states", ()),
        measurement_references=getattr(
            snapshot, "measurement_references", ()
        ),
        regions_migration=getattr(snapshot, "regions_migration", None),
        journeys=getattr(snapshot, "journeys", None),
        disease_state=_disease_state_from_snapshot(snapshot),
        ecological_resources=_ecological_resources_from_snapshot(snapshot),
        ecological_policy_digest=_ecological_digest_from_snapshot(snapshot),
    )


def _ecological_resources_from_snapshot(
    snapshot: object,
) -> dict[EntityId, EcologicalStockRow] | None:
    section = getattr(snapshot, "ecological_resources", None)
    if section is None:
        return None
    return {
        row.resource_id: EcologicalStockRow(
            resource_id=row.resource_id,
            minimum_capacity_tenths=row.minimum_capacity_tenths,
            damage_tenths=row.damage_tenths,
        )
        for row in section.rows
    }


def _ecological_digest_from_snapshot(snapshot: object) -> str | None:
    section = getattr(snapshot, "ecological_resources", None)
    if section is None:
        return None
    digest = section.policy_sha256
    if type(digest) is not str:
        raise TypeError("ecological checkpoint policy_sha256 must be str")
    return digest


def _materialize_projected_world(*, world_id: WorldId, state: object) -> World:
    """Internal: wrap a projected ``WorldState`` without a mutation hook."""
    from world._state import World, WorldState

    if type(world_id) is not WorldId:
        raise TypeError("world_id must be WorldId")
    if type(state) is not WorldState:
        raise TypeError("state must be WorldState")
    return World(world_id, state)


def _translator_from_registrations(
    registrations: Sequence[AgentRegistration],
) -> RegistrationTranslator:
    forward: dict[AgentId, EntityId] = {}
    reverse: dict[EntityId, AgentId] = {}
    order = tuple(registrations)
    for registration in order:
        if registration.agent_id in forward:
            raise ValueError(
                f"duplicate agent_id in registrations {registration.agent_id.value!r}"
            )
        if registration.entity_id in reverse:
            raise ValueError(
                f"duplicate entity_id in registrations {registration.entity_id.value!r}"
            )
        forward[registration.agent_id] = registration.entity_id
        reverse[registration.entity_id] = registration.agent_id
    return RegistrationTranslator(
        _forward=MappingProxyType(forward),
        _reverse=MappingProxyType(reverse),
        _order=order,
    )


def _validate_registrations_against_models(
    *,
    locations: Sequence[Location],
    items: Sequence[Item],
    resources: Sequence[Resource],
    bodies: Sequence[AgentBody],
    registrations: Sequence[AgentRegistration],
    artifacts: Sequence[InformationArtifact] = (),
) -> None:
    body_ids = {body.entity_id for body in bodies}
    location_ids = {location.entity_id for location in locations}
    item_ids = {item.entity_id for item in items}
    resource_ids = {resource.entity_id for resource in resources}
    artifact_ids = {artifact.artifact_id for artifact in artifacts}
    _translator_from_registrations(registrations)
    for registration in registrations:
        entity_id = registration.entity_id
        if entity_id in location_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} refers to a location"
            )
        if entity_id in item_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} refers to an item"
            )
        if entity_id in resource_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} refers to a resource"
            )
        if entity_id in artifact_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} refers to an artifact"
            )
        if entity_id not in body_ids:
            raise ValueError(
                f"registration entity_id {entity_id.value!r} has no matching body"
            )


def _copy_models[T](
    name: str, values: Sequence[T], *, model_type: type[T]
) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for value in copied:
        if type(value) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
    return copied


def _copy_registrations(
    name: str, values: Sequence[AgentRegistration]
) -> tuple[AgentRegistration, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for value in copied:
        if type(value) is not AgentRegistration:
            raise TypeError(f"{name} entries must be AgentRegistration")
    return copied
