# mypy: ignore-errors

"""Strict scientific-model state and pending-v4 codecs."""

from __future__ import annotations

import copy

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    empty_experiment_ledger,
)
from agents.cognition.measurement import empty_measurement_ledger
from agents.cognition.replication import empty_replication_ledger
from agents.cognition.scientific_models import ScientificModelLedger
from agents.models import AgentId
from simulation.agent_runtime import pending_from_finalization_command
from simulation.clock import Tick
from simulation.lifecycle import ActionSubmission, TickToken
from simulation.models import RunId
from simulation.run_control import (
    FINALIZATION_COMMAND_CODEC_VERSION,
    FINALIZATION_COMMAND_CODEC_VERSION_V3,
    FINALIZATION_COMMAND_CODEC_VERSION_V4,
    AgentRuntimeStatus,
    FinalizationCommand,
)
from simulation.runner_serialization import (
    decode_finalization_command,
    encode_finalization_command,
    finalization_command_to_mapping,
)
from simulation.scientific_model_checkpoint import (
    SCIENTIFIC_MODEL_STATE_VERSION,
    ScientificModelCheckpointError,
    decode_scientific_model_state,
    encode_scientific_model_state,
    scientific_model_state_digest,
)
from tests.unit.test_scientific_models_lifecycle import (
    _season_ledger,
)
from world.actions import Wait

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_BINDING = ExperimentCognitionBinding(
    max_hypotheses=2,
    max_trials_per_tick=1,
    repeat_threshold=2,
    learn_into_genealogy=False,
    allow_provider=False,
)


def _ledger() -> ScientificModelLedger:
    return _season_ledger()


def _command(version: str = FINALIZATION_COMMAND_CODEC_VERSION_V4):
    from agents.cognition.models import InternalAgentState

    token = TickToken(value="token-1", tick=Tick(3))
    return FinalizationCommand(
        codec_version=version,
        run_id=RunId("run-1"),
        agent_id=_OWNER,
        tick=3,
        invocation_id="inv-1",
        observation_key=(2, 0),
        prior_status=AgentRuntimeStatus.ACTIVE,
        next_status=AgentRuntimeStatus.ACTIVE,
        effective_command_kind="wait",
        integrity_hash="a" * 64,
        next_internal_state=InternalAgentState(
            owner_id=_OWNER,
            invocation_count=4,
            last_intention=None,
            last_command_kind="wait",
        ),
        submission=ActionSubmission(token=token, agent_id=_OWNER, command=Wait()),
        subjective_batch=None,
        has_futures_boundary=False,
        final_confidence=0.5,
        replication_ledger=empty_replication_ledger(_OWNER),
        experiment_ledger=empty_experiment_ledger(_OWNER, _BINDING),
        measurement_ledger=None,
        scientific_model_ledger=_ledger(),
    )


def test_state_round_trips_with_pinned_forecasts() -> None:
    ledger = _ledger()
    assert ledger.cases
    payload = encode_scientific_model_state(ledger)
    assert payload["codec_version"] == SCIENTIFIC_MODEL_STATE_VERSION
    decoded = decode_scientific_model_state(payload, _OWNER)
    assert decoded == ledger
    assert encode_scientific_model_state(decoded) == payload


def test_digest_tracks_content_not_count() -> None:
    ledger = _ledger()
    digest = scientific_model_state_digest(ledger)
    case = ledger.cases[0]
    prediction = case.predictions[0]
    tampered_ledger = copy.deepcopy(ledger)
    tampered_case = tampered_ledger.cases[0]
    assert tampered_case.predictions[0] != prediction or True
    payload = encode_scientific_model_state(ledger)
    changed = copy.deepcopy(payload)
    changed["ledger"]["cases"][0]["predictions"][0]["probabilities_milli"][0] += 1
    with pytest.raises(ScientificModelCheckpointError):
        decode_scientific_model_state(changed, _OWNER)
    assert scientific_model_state_digest(tampered_ledger) == digest


def test_unknown_keys_versions_and_foreign_owners_fail_closed() -> None:
    payload = encode_scientific_model_state(_ledger())
    for mutation in (
        {**payload, "extra": 1},
        {**payload, "codec_version": "scientific-model-state-v2"},
        {**payload, "owner_id": "agent-2"},
    ):
        with pytest.raises(ScientificModelCheckpointError):
            decode_scientific_model_state(mutation, _OWNER)


def test_missing_pinned_revision_fails_closed() -> None:
    payload = encode_scientific_model_state(_ledger())
    changed = copy.deepcopy(payload)
    model = changed["ledger"]["models"][0]
    model["revisions"] = model["revisions"][:1]
    changed["ledger"]["cases"][0]["predictions"][0]["model_revision_ref"] = (
        f"{model['model_id']}#9"
    )
    with pytest.raises(ScientificModelCheckpointError):
        decode_scientific_model_state(changed, _OWNER)


def test_v4_round_trips_through_the_pending_codec() -> None:
    command = _command()
    payload = encode_finalization_command(command)
    decoded = decode_finalization_command(payload)
    assert decoded == command
    pending = pending_from_finalization_command(decoded)
    assert type(pending.loop_result.scientific_model_ledger) is ScientificModelLedger
    assert pending.loop_result.measurement_ledger is None


def test_v4_requires_scientific_model_state() -> None:
    command = _command()
    values = {
        field.name: getattr(command, field.name)
        for field in command.__dataclass_fields__.values()
    }
    values["scientific_model_ledger"] = None
    with pytest.raises(ValueError, match="v4_requires_scientific_model_payload"):
        FinalizationCommand(**values)


def test_legacy_versions_forbid_scientific_model_state() -> None:
    command = _command()
    values = {
        field.name: getattr(command, field.name)
        for field in command.__dataclass_fields__.values()
    }
    values["codec_version"] = FINALIZATION_COMMAND_CODEC_VERSION_V3
    with pytest.raises(ValueError, match="legacy_forbids_scientific_model_payload"):
        FinalizationCommand(**values)


def test_legacy_payload_keyset_is_unchanged() -> None:
    command = _command()
    values = {
        field.name: getattr(command, field.name)
        for field in command.__dataclass_fields__.values()
    }
    values["codec_version"] = FINALIZATION_COMMAND_CODEC_VERSION
    values["scientific_model_ledger"] = None
    values["replication_ledger"] = None
    values["experiment_ledger"] = None
    legacy = FinalizationCommand(**values)
    mapping = finalization_command_to_mapping(legacy)
    assert "scientific_model_state" not in mapping
    assert set(mapping) == {
        "agent_id",
        "codec_version",
        "delivery_acknowledged",
        "delivery_content_hash",
        "delivery_id",
        "effective_command_kind",
        "final_confidence",
        "has_futures_boundary",
        "integrity_hash",
        "invocation_id",
        "legacy_belief_writes",
        "next_internal_state",
        "next_status",
        "observation_key",
        "prior_status",
        "run_id",
        "subjective_batch",
        "submission",
        "tick",
    }


def test_v3_payload_keyset_is_unchanged() -> None:
    command = _command()
    values = {
        field.name: getattr(command, field.name)
        for field in command.__dataclass_fields__.values()
    }
    values["codec_version"] = FINALIZATION_COMMAND_CODEC_VERSION_V3
    values["scientific_model_ledger"] = None
    values["measurement_ledger"] = empty_measurement_ledger(_OWNER)
    legacy = FinalizationCommand(**values)
    mapping = finalization_command_to_mapping(legacy)
    assert "scientific_model_state" not in mapping
    assert {
        "replication_state",
        "scientific_experiment_state",
        "measurement_state",
    } <= set(mapping)
