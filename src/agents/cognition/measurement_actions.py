"""Owner-safe measurement evidence projection and conservative instrument actions."""

from __future__ import annotations

import logging
from typing import Final

from agents.cognition.measurement import (
    InstrumentReliabilityBelief,
    MeasurementLedger,
)
from world.actions import CalibrateInstrument, Measure
from world.identifiers import EntityId
from world.measurement import MeasurementQuantity
from world.observations import (
    Observation,
    ObservedItemPlacement,
)

__all__ = [
    "compile_measurement_action",
    "measurement_evidence_candidates",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.measurement_actions"
)


def measurement_evidence_candidates(
    ledger: MeasurementLedger, observation: Observation
) -> tuple[object, ...]:
    """Return at most four direct-measurement evidence anchors. Never writes."""
    if type(ledger) is not MeasurementLedger:
        raise TypeError("ledger must be MeasurementLedger")
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    from agents.cognition.evidence_testimony import (
        EvidenceObservedReference,
        EvidenceReferenceKind,
    )

    candidates: list[object] = []
    for evidence in ledger.evidence:
        if evidence.source_kind != "own_observation":
            continue
        candidates.append(
            EvidenceObservedReference(
                reference_kind=EvidenceReferenceKind.OBSERVED_OCCURRENCE,
                reference_id=evidence.evidence_id,
                tick=evidence.observed_tick,
                correlation_id=evidence.source_event_id,
                actor_id=evidence.owner_id.value,
                location_token=evidence.target_id.value,
                ordinal=len(candidates),
                owner_id=evidence.owner_id.value,
            )
        )
        if len(candidates) == 4:
            break
    return tuple(candidates)


def _belief(
    ledger: MeasurementLedger, instrument_id: EntityId
) -> InstrumentReliabilityBelief | None:
    return next(
        (row for row in ledger.beliefs if row.instrument_id == instrument_id),
        None,
    )


def _target_for(
    observation: Observation,
    quantity: MeasurementQuantity,
    instrument_id: EntityId,
) -> EntityId | None:
    if quantity is MeasurementQuantity.AMBIENT_TEMPERATURE:
        return (
            None
            if observation.self_body is None
            else observation.self_body.location_id
        )
    if quantity is MeasurementQuantity.ELAPSED_DURATION:
        return instrument_id
    if quantity is MeasurementQuantity.TRAVEL_TIME_ESTIMATE:
        return min(
            (exit_.destination_id for exit_ in observation.exits),
            key=lambda item: item.value,
            default=None,
        )
    if quantity is MeasurementQuantity.RESOURCE_AMOUNT:
        return min(
            (row.entity_id for row in observation.resources),
            key=lambda item: item.value,
            default=None,
        )
    if quantity is MeasurementQuantity.LOAD_CATEGORY:
        return min(
            (row.entity_id for row in observation.items),
            key=lambda item: item.value,
            default=None,
        )
    return None


def compile_measurement_action(
    observation: Observation,
    ledger: MeasurementLedger,
    *,
    tick: int,
) -> object | None:
    """Return one ordinary instrument command or a legal null.

    Existing non-Wait actions, replication actions and hypothesis-test actions
    are selected elsewhere and keep precedence over this lowest-priority seam.
    """
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(ledger) is not MeasurementLedger:
        raise TypeError("ledger must be MeasurementLedger")
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise ValueError("tick must be non-negative")
    instruments = sorted(
        (
            row
            for row in observation.items
            if row.instrument is not None
            and row.placement is ObservedItemPlacement.HELD_BY_SELF
        ),
        key=lambda row: row.entity_id.value,
    )
    if not instruments:
        return None
    references = sorted(
        (
            row
            for row in observation.items
            if row.reference is not None
            and row.placement
            in {
                ObservedItemPlacement.HELD_BY_SELF,
                ObservedItemPlacement.GROUND_HERE,
            }
        ),
        key=lambda row: row.entity_id.value,
    )
    if tick % 16 == 0:
        for item in instruments:
            appearance = item.instrument
            assert appearance is not None
            belief = _belief(ledger, item.entity_id)
            if belief is None or belief.confidence_milli > 300:
                continue
            matching = next(
                (
                    reference
                    for reference in references
                    if reference.reference is not None
                    and reference.reference.unit == appearance.unit
                ),
                None,
            )
            if matching is None:
                continue
            return CalibrateInstrument(item.entity_id, matching.entity_id)
    if tick % 4 != 0:
        return None
    for item in instruments:
        appearance = item.instrument
        assert appearance is not None
        target = _target_for(observation, appearance.quantity, item.entity_id)
        if target is None:
            continue
        return Measure(item.entity_id, target, appearance.quantity)
    return None
