"""Pure checkpoint-plus-event fold for objective population metadata.

Historical body/physics projection is owned by ``world._replay``. This module
only reconstructs the detached registration/lifecycle metadata that the
read-only observer needs, using the same deterministic entry rules as the live
engine. It never invokes cognition, demographic policy, or mortality.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, NoReturn

from agents.models import AgentId
from simulation.lifespan_distribution import assign_lifespan_ticks
from simulation.models import SimulationRunConfig
from simulation.registrations import AgentRegistration
from simulation.runner_models import PopulationLifecycleSpec
from world.events import (
    AgentCreated,
    AgentEnteredWorld,
    AgentInitializationRecorded,
    LifecycleStageChanged,
    WorldEvent,
)
from world.identifiers import EntityId
from world.lifecycle import (
    AgentLifecycleRecord,
    DependencyStatus,
    LifecycleStageId,
    OriginProvenance,
    resolve_dependency_status,
    resolve_lifecycle_stage,
)

_LOGGER: Final[logging.Logger] = logging.getLogger(
    "simulation.population_replay"
)

__all__ = [
    "PendingPopulationReservation",
    "PopulationMetadataError",
    "PopulationMetadataFold",
    "fold_population_metadata",
]

_POPULATION_DETAILS = (
    AgentCreated,
    AgentInitializationRecorded,
    AgentEnteredWorld,
    LifecycleStageChanged,
)


class PopulationMetadataError(ValueError):
    """Closed failure while folding historical population metadata."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _reject(reason_code: str) -> NoReturn:
    _LOGGER.error("population_metadata_rejected reason_code=%s", reason_code)
    raise PopulationMetadataError(reason_code)


@dataclass(frozen=True, slots=True)
class PendingPopulationReservation:
    """An ``AgentCreated`` identity that has not entered the world yet."""

    body_id: EntityId
    agent_id: str
    entry_tick: int
    generation_index: int
    cohort_id: str
    provenance: OriginProvenance
    initialization_recorded: bool = False

    def __post_init__(self) -> None:
        if type(self.body_id) is not EntityId:
            raise TypeError("body_id must be EntityId")
        if type(self.provenance) is not OriginProvenance:
            raise TypeError("provenance must be OriginProvenance")
        if type(self.initialization_recorded) is not bool:
            raise TypeError("initialization_recorded must be bool")


@dataclass(frozen=True, slots=True)
class PopulationMetadataFold:
    """Folded metadata plus reservations that never reached ``AgentEnteredWorld``."""

    registrations: tuple[AgentRegistration, ...]
    lifecycle_records: tuple[AgentLifecycleRecord, ...]
    pending_reservations: tuple[PendingPopulationReservation, ...] = ()

    def __post_init__(self) -> None:
        if any(
            type(item) is not AgentRegistration for item in self.registrations
        ):
            raise TypeError("registrations entries must be AgentRegistration")
        if any(
            type(item) is not AgentLifecycleRecord
            for item in self.lifecycle_records
        ):
            raise TypeError("lifecycle_records entries must be AgentLifecycleRecord")
        if any(
            type(item) is not PendingPopulationReservation
            for item in self.pending_reservations
        ):
            raise TypeError(
                "pending_reservations entries must be PendingPopulationReservation"
            )


def fold_population_metadata(
    *,
    registrations: Sequence[object],
    lifecycle_records: Sequence[object],
    events: Sequence[WorldEvent],
    population_lifecycle: PopulationLifecycleSpec | None,
    run_config: SimulationRunConfig,
    run_id: str,
    world_id: str,
) -> PopulationMetadataFold:
    """Fold committed population events onto checkpoint metadata.

    ``AgentCreated`` reserves identity, ``AgentInitializationRecorded`` is a
    witness, ``AgentEnteredWorld`` admits the registration and lifecycle
    record, and ``LifecycleStageChanged`` replaces the recorded stage. Events
    are applied once; folding the same events twice fails closed.
    """
    if (
        isinstance(registrations, (str, bytes, set, frozenset))
        or not isinstance(registrations, Sequence)
    ):
        raise TypeError("registrations must be an ordered sequence")
    if (
        isinstance(lifecycle_records, (str, bytes, set, frozenset))
        or not isinstance(lifecycle_records, Sequence)
    ):
        raise TypeError("lifecycle_records must be an ordered sequence")
    if isinstance(events, (str, bytes, set, frozenset)) or not isinstance(
        events, Sequence
    ):
        raise TypeError("events must be an ordered sequence")
    if type(run_config) is not SimulationRunConfig:
        raise TypeError("run_config must be SimulationRunConfig")
    if population_lifecycle is not None and (
        type(population_lifecycle) is not PopulationLifecycleSpec
    ):
        raise TypeError("population_lifecycle must be PopulationLifecycleSpec or None")

    ordered_registrations: list[AgentRegistration] = []
    registrations_by_body: dict[str, AgentRegistration] = {}
    registrations_by_agent: dict[str, AgentRegistration] = {}
    for registration in registrations:
        if type(registration) is not AgentRegistration:
            raise TypeError("registrations entries must be AgentRegistration")
        if registration.entity_id.value in registrations_by_body:
            _reject("population_metadata_duplicate_body")
        if registration.agent_id.value in registrations_by_agent:
            _reject("population_metadata_duplicate_agent")
        registrations_by_body[registration.entity_id.value] = registration
        registrations_by_agent[registration.agent_id.value] = registration
        ordered_registrations.append(registration)

    ordered_records: list[AgentLifecycleRecord] = []
    records_by_body: dict[str, AgentLifecycleRecord] = {}
    for record in lifecycle_records:
        if type(record) is not AgentLifecycleRecord:
            raise TypeError("lifecycle_records entries must be AgentLifecycleRecord")
        if record.body_id.value in records_by_body:
            _reject("population_metadata_duplicate_lifecycle")
        registration = registrations_by_body.get(record.body_id.value)
        if registration is None:
            _reject("population_metadata_lifecycle_body_missing")
        if registration.agent_id.value != record.agent_id:
            _reject("population_metadata_identity_mismatch")
        records_by_body[record.body_id.value] = record
        ordered_records.append(record)

    population_details = tuple(
        event for event in events if type(event.details) in _POPULATION_DETAILS
    )
    if population_lifecycle is None:
        if ordered_records or population_details:
            _reject("lifecycle_channel_off")
        return PopulationMetadataFold(
            registrations=tuple(ordered_registrations),
            lifecycle_records=(),
        )

    spec = population_lifecycle
    pending: dict[str, PendingPopulationReservation] = {}
    pending_by_agent: dict[str, str] = {}
    previous_key: tuple[int, int] | None = None

    for event in events:
        key = (event.tick, event.sequence)
        if previous_key is not None and key <= previous_key:
            _reject("population_metadata_event_order")
        previous_key = key
        details = event.details
        if type(details) is AgentCreated:
            body_key = details.body_id.value
            agent_key = details.agent_id
            if body_key in registrations_by_body or body_key in pending:
                _reject("population_metadata_duplicate_created")
            if agent_key in registrations_by_agent or agent_key in pending_by_agent:
                _reject("population_metadata_duplicate_agent")
            pending[body_key] = PendingPopulationReservation(
                body_id=details.body_id,
                agent_id=agent_key,
                entry_tick=event.tick,
                generation_index=details.generation_index,
                cohort_id=details.cohort_id,
                provenance=OriginProvenance(details.provenance),
            )
            pending_by_agent[agent_key] = body_key
            _LOGGER.debug(
                "population_metadata_reserved body_id=%s agent_id=%s tick=%s "
                "generation_index=%s",
                body_key,
                agent_key,
                event.tick,
                details.generation_index,
            )
        elif type(details) is AgentInitializationRecorded:
            reservation = pending.get(details.body_id.value)
            if reservation is None:
                _reject("population_metadata_orphan_initialization")
            if reservation.agent_id != details.agent_id:
                _reject("population_metadata_identity_mismatch")
            if reservation.initialization_recorded:
                _reject("population_metadata_duplicate_initialization")
            pending[details.body_id.value] = PendingPopulationReservation(
                body_id=reservation.body_id,
                agent_id=reservation.agent_id,
                entry_tick=reservation.entry_tick,
                generation_index=reservation.generation_index,
                cohort_id=reservation.cohort_id,
                provenance=reservation.provenance,
                initialization_recorded=True,
            )
            _LOGGER.debug(
                "population_metadata_initialization_witness body_id=%s tick=%s",
                details.body_id.value,
                event.tick,
            )
        elif type(details) is AgentEnteredWorld:
            body_key = details.body_id.value
            reservation = pending.get(body_key)
            if reservation is None:
                _reject("population_metadata_missing_created")
            if reservation.agent_id != details.agent_id:
                _reject("population_metadata_identity_mismatch")
            if body_key in registrations_by_body:
                _reject("population_metadata_duplicate_entry")
            stage = resolve_lifecycle_stage(0, spec.stage_thresholds)
            dependency = resolve_dependency_status(
                stage,
                spec.dependent_until_stage,
                stage_order=spec.stage_order,
            )
            assigned = assign_lifespan_ticks(
                spec=spec,
                run_config=run_config,
                run_id=run_id,
                world_id=world_id,
                agent_id=reservation.agent_id,
                entry_tick=details.entry_tick,
            )
            record = AgentLifecycleRecord(
                body_id=details.body_id,
                agent_id=reservation.agent_id,
                entry_tick=details.entry_tick,
                stage=stage,
                dependency_status=dependency,
                generation_index=reservation.generation_index,
                cohort_id=reservation.cohort_id,
                provenance=reservation.provenance,
                assigned_lifespan_ticks=assigned,
            )
            registration = AgentRegistration(
                agent_id=AgentId(reservation.agent_id),
                entity_id=details.body_id,
            )
            ordered_registrations.append(registration)
            registrations_by_body[body_key] = registration
            registrations_by_agent[reservation.agent_id] = registration
            records_by_body[body_key] = record
            ordered_records.append(record)
            del pending[body_key]
            pending_by_agent.pop(reservation.agent_id, None)
            _LOGGER.debug(
                "population_metadata_entered body_id=%s agent_id=%s entry_tick=%s "
                "generation_index=%s",
                body_key,
                reservation.agent_id,
                details.entry_tick,
                reservation.generation_index,
            )
        elif type(details) is LifecycleStageChanged:
            body_key = details.body_id.value
            record = records_by_body.get(body_key)
            if record is None:
                _reject("population_metadata_missing_stage_record")
            if details.previous_stage != record.stage.value:
                _reject("population_metadata_stage_mismatch")
            updated = AgentLifecycleRecord(
                body_id=record.body_id,
                agent_id=record.agent_id,
                entry_tick=record.entry_tick,
                stage=LifecycleStageId(details.new_stage),
                dependency_status=DependencyStatus(details.dependency_status),
                generation_index=record.generation_index,
                cohort_id=record.cohort_id,
                provenance=record.provenance,
                assigned_lifespan_ticks=record.assigned_lifespan_ticks,
            )
            records_by_body[body_key] = updated
            ordered_records = [
                updated if item.body_id == updated.body_id else item
                for item in ordered_records
            ]
            _LOGGER.debug(
                "population_metadata_stage_changed body_id=%s previous_stage=%s "
                "new_stage=%s tick=%s",
                body_key,
                details.previous_stage,
                details.new_stage,
                event.tick,
            )

    pending_rows = tuple(
        sorted(pending.values(), key=lambda item: (item.entry_tick, item.agent_id))
    )
    _LOGGER.debug(
        "population_metadata_folded registration_count=%s lifecycle_count=%s "
        "pending_count=%s event_count=%s",
        len(ordered_registrations),
        len(ordered_records),
        len(pending_rows),
        len(events),
    )
    return PopulationMetadataFold(
        registrations=tuple(ordered_registrations),
        lifecycle_records=tuple(ordered_records),
        pending_reservations=pending_rows,
    )
