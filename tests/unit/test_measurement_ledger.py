# mypy: ignore-errors

"""Bounded owner measurement evidence and mistaken reliability beliefs."""

from __future__ import annotations

import pytest

from agents.cognition.measurement import (
    MAX_EVIDENCE_ROWS,
    MeasurementEvidence,
    compare_measurement_evidence,
    empty_measurement_ledger,
    ingest_measurement_observations,
)
from agents.models import AgentId
from tests.simulation_helpers import alive_body
from world.environment import Season, TemperatureBand
from world.identifiers import EntityId, EventId, WorldRevision
from world.measurement import (
    MeasurementQuantity,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    observed_self_from_body,
)
from world.values import DayPhase, WeatherCondition

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_BODY = EntityId("body-1")
_TOOL = EntityId("item-thermometer")
_TARGET = EntityId("loc-1")
_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)


def _occurrence(
    *,
    event_id: str,
    tick: int = 1,
    display: int = 15000,
    kind: str = "measurement_taken",
    role: ObservationAudienceRole = ObservationAudienceRole.ACTOR,
) -> ObservedOccurrence:
    facts = {
        "kind": kind,
        "instrument_id": _TOOL.value,
        "target_id": _TARGET.value,
        "quantity": MeasurementQuantity.AMBIENT_TEMPERATURE.value,
        "unit_kind": MeasurementUnitKind.CELSIUS.value,
        "unit_resource": None,
        "value_kind": "scalar",
        "display_scalar_milli": display,
        "nominal_division_milli": 1000,
        "sample_tick": tick,
    }
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(event_id),
        ),
        kind="measurement_taken",
        audience_role=role,
        actor_id=_BODY,
        other_entity_id=_TARGET,
        public_facts=facts,
    )


def _observation(
    *occurrences: ObservedOccurrence,
    day_phase: DayPhase = DayPhase.DAY,
    weather: WeatherCondition = WeatherCondition.CLEAR,
    season: Season = Season.SPRING,
) -> Observation:
    body = alive_body("body-1")
    observation_tick = (
        max(
            (
                occurrence.provenance.source_tick
                for occurrence in occurrences
            ),
            default=0,
        )
        + 1
    )
    return Observation(
        world_id=__import__("world.identifiers", fromlist=["WorldId"]).WorldId(
            "world-1"
        ),
        observer_id=_BODY,
        revision=WorldRevision(0),
        tick=observation_tick,
        self_body=observed_self_from_body(body),
        occurrences=occurrences,
        day_phase=day_phase,
        weather_condition=weather,
        season=season,
        temperature_band=TemperatureBand.MILD,
    )


def test_first_reading_seeds_uncertainty_and_unknown_error() -> None:
    ledger = ingest_measurement_observations(
        empty_measurement_ledger(_OWNER), _observation(_occurrence(event_id="e1"))
    )
    assert len(ledger.evidence) == 1
    belief = ledger.beliefs[0]
    assert belief.confidence_milli == 500
    assert belief.estimated_error_band_milli is None
    assert belief.expected_resolution_milli == 1000
    assert ledger.revisions[0].agreement == "initial"


def test_duplicate_source_is_idempotent() -> None:
    first = ingest_measurement_observations(
        empty_measurement_ledger(_OWNER), _observation(_occurrence(event_id="e1"))
    )
    second = ingest_measurement_observations(
        first, _observation(_occurrence(event_id="e1"))
    )
    assert second == first


def test_observed_wear_and_adjustment_mark_update_belief_cues() -> None:
    evidence = MeasurementEvidence(
        evidence_id="mev:" + "a" * 32,
        owner_id=_OWNER,
        instrument_id=_TOOL,
        target_id=_TARGET,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        value_kind="scalar",
        displayed_scalar_milli=15000,
        displayed_category=None,
        nominal_division_milli=1000,
        observed_tick=4,
        source_kind="own_observation",
        source_event_id="e" * 64,
        delivery_event_id=None,
        declared_root="e" * 64,
        observed_wear="worn",
        adjustment_mark_present=True,
    )
    ledger = compare_measurement_evidence(
        empty_measurement_ledger(_OWNER), evidence
    )
    assert ledger.beliefs[0].observed_wear == "worn"
    assert ledger.beliefs[0].adjustment_mark_present is True


def test_consistent_biased_readings_increase_confidence_without_truth() -> None:
    ledger = empty_measurement_ledger(_OWNER)
    for index, tick in enumerate((1, 2, 3)):
        ledger = ingest_measurement_observations(
            ledger,
            _observation(
                _occurrence(event_id=f"e{index}", tick=tick, display=21000)
            ),
        )
    assert ledger.beliefs[0].confidence_milli == 600
    assert ledger.beliefs[0].estimated_error_band_milli == 1000
    assert "intrinsic_bias" not in repr(ledger).lower()


def test_disagreement_lowers_confidence_and_preserves_contradiction() -> None:
    ledger = empty_measurement_ledger(_OWNER)
    for index, (tick, display) in enumerate(((1, 15000), (2, 19000))):
        ledger = ingest_measurement_observations(
            ledger,
            _observation(
                _occurrence(event_id=f"e{index}", tick=tick, display=display)
            ),
        )
    assert ledger.beliefs[0].confidence_milli == 400
    assert [row.agreement for row in ledger.revisions] == [
        "initial",
        "disagreement",
    ]


def test_unknown_or_changed_conditions_leave_confidence_unchanged() -> None:
    ledger = empty_measurement_ledger(_OWNER)
    ledger = ingest_measurement_observations(
        ledger, _observation(_occurrence(event_id="e1", display=15000))
    )
    ledger = ingest_measurement_observations(
        ledger,
        _observation(
            _occurrence(event_id="e2", tick=2, display=19000),
            weather=WeatherCondition.STORM,
        ),
    )
    assert ledger.beliefs[0].confidence_milli == 500
    assert ledger.revisions[-1].agreement == "no_comparison"


def test_bystander_occurrence_is_not_direct_evidence() -> None:
    ledger = ingest_measurement_observations(
        empty_measurement_ledger(_OWNER),
        _observation(
            _occurrence(
                event_id="e1", role=ObservationAudienceRole.BYSTANDER
            )
        ),
    )
    assert ledger.evidence == ()
    assert ledger.beliefs == ()


def test_owner_mismatch_is_rejected() -> None:
    ledger = empty_measurement_ledger(_OWNER)
    evidence = MeasurementEvidence(
        evidence_id="mev:1",
        owner_id=AgentId("agent-2"),
        instrument_id=_TOOL,
        target_id=_TARGET,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        value_kind="scalar",
        displayed_scalar_milli=15000,
        displayed_category=None,
        nominal_division_milli=1000,
        observed_tick=1,
        source_kind="own_observation",
        source_event_id="e1",
        delivery_event_id=None,
        declared_root="e1",
    )
    from agents.cognition.measurement import compare_measurement_evidence

    with pytest.raises(ValueError, match="owner_mismatch"):
        compare_measurement_evidence(ledger, evidence)


def test_evidence_retention_is_bounded_and_deterministic() -> None:
    ledger = empty_measurement_ledger(_OWNER)
    for index in range(MAX_EVIDENCE_ROWS + 5):
        ledger = ingest_measurement_observations(
            ledger,
            _observation(_occurrence(event_id=f"e{index}", tick=index)),
        )
    assert len(ledger.evidence) == MAX_EVIDENCE_ROWS
    assert [row.observed_tick for row in ledger.evidence] == sorted(
        row.observed_tick for row in ledger.evidence
    )
