# mypy: ignore-errors

"""Strict ``measurement-state-v1`` envelope and pending-v3 acceptance."""

from __future__ import annotations

import pytest

from agents.cognition.measurement import (
    InstrumentReliabilityBelief,
    MeasurementEvidence,
    MeasurementLedger,
    empty_measurement_ledger,
)
from agents.models import AgentId
from simulation.measurement_checkpoint import (
    MeasurementCheckpointError,
    decode_measurement_state,
    encode_measurement_state,
    measurement_state_digest,
)
from simulation.persistence import PENDING_FINALIZATION_ACCEPTED_VERSIONS
from simulation.run_control import (
    FINALIZATION_COMMAND_ACCEPTED_VERSIONS,
    FINALIZATION_COMMAND_CODEC_VERSION_V3,
)
from world.identifiers import EntityId
from world.measurement import (
    MeasurementQuantity,
    MeasurementUnit,
    MeasurementUnitKind,
)

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_TOOL = EntityId("item-thermometer")
_TARGET = EntityId("loc-1")
_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)


def _ledger() -> MeasurementLedger:
    return MeasurementLedger(
        owner_id=_OWNER,
        evidence=(
            MeasurementEvidence(
                evidence_id="mev:1",
                owner_id=_OWNER,
                instrument_id=_TOOL,
                target_id=_TARGET,
                quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
                unit=_CELSIUS,
                value_kind="scalar",
                displayed_scalar_milli=15000,
                displayed_category=None,
                nominal_division_milli=1000,
                observed_tick=2,
                source_kind="own_observation",
                source_event_id="e" * 64,
                delivery_event_id=None,
                declared_root="e" * 64,
                condition_tokens=("weather_condition:clear",),
            ),
        ),
        beliefs=(
            InstrumentReliabilityBelief(
                instrument_id=_TOOL,
                quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
                unit=_CELSIUS,
                expected_resolution_milli=1000,
                estimated_error_band_milli=None,
                confidence_milli=500,
                observed_wear="intact",
                adjustment_mark_present=False,
                evidence_ids=("mev:1",),
            ),
        ),
        receipts=("own:" + "e" * 64,),
    )


def test_round_trip_and_digest_are_deterministic() -> None:
    ledger = _ledger()
    payload = encode_measurement_state(ledger)
    assert set(payload) == {
        "codec_version",
        "owner_id",
        "policy_version",
        "ledger",
    }
    assert decode_measurement_state(payload, _OWNER) == ledger
    assert measurement_state_digest(ledger) == measurement_state_digest(
        decode_measurement_state(payload, _OWNER)
    )


def test_empty_ledger_is_explicit_not_absent() -> None:
    ledger = empty_measurement_ledger(_OWNER)
    payload = encode_measurement_state(ledger)
    assert payload["ledger"]["evidence"] == []
    assert decode_measurement_state(payload, _OWNER) == ledger


def test_wrong_owner_version_and_tampering_fail_closed() -> None:
    payload = encode_measurement_state(_ledger())
    with pytest.raises(MeasurementCheckpointError, match="owner_mismatch"):
        decode_measurement_state(payload, AgentId("agent-2"))
    broken = {**payload, "codec_version": "measurement-state-v0"}
    with pytest.raises(MeasurementCheckpointError, match="unsupported_version"):
        decode_measurement_state(broken, _OWNER)
    tampered = {
        **payload,
        "ledger": {
            **payload["ledger"],
            "receipts": list(payload["ledger"]["receipts"]) * 2,
        },
    }
    with pytest.raises(MeasurementCheckpointError, match="invalid_value"):
        decode_measurement_state(tampered, _OWNER)


def test_pending_v3_is_accepted_in_both_mirrors() -> None:
    assert (
        FINALIZATION_COMMAND_CODEC_VERSION_V3 in FINALIZATION_COMMAND_ACCEPTED_VERSIONS
    )
    assert (
        FINALIZATION_COMMAND_CODEC_VERSION_V3 in PENDING_FINALIZATION_ACCEPTED_VERSIONS
    )
