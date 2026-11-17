# mypy: ignore-errors
"""V4-28 private science/replication checkpoint codecs."""

from __future__ import annotations

import pytest

from agents.cognition import (
    ExperimentSelector,
    ReplicationBindingMode,
    ReplicationCollaboration,
    ReplicationSelectorFamily,
    adopt_replication_design,
    append_replication_design,
    build_experiment_design,
    empty_experiment_ledger,
    empty_replication_ledger,
    open_replication_collaboration,
    replication_ref,
)
from agents.cognition.experimentation import ExperimentCognitionBinding
from agents.models import AgentId
from simulation.replication_checkpoint import (
    REPLICATION_STATE_VERSION,
    ReplicationCheckpointError,
    decode_replication_state,
    decode_scientific_experiment_state,
    encode_replication_state,
    encode_scientific_experiment_state,
    replication_state_digest,
    scientific_experiment_state_digest,
)
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("owner-1")
OTHER = AgentId("owner-2")


def _ledger() -> object:
    design = build_experiment_design(
        origin_token=replication_ref("rorg", OWNER.value, "trial"),
        parent_design_token=None,
        source_hypothesis_token=replication_ref("rhyp", OWNER.value, "hyp"),
        source_trial_token=replication_ref("rtrl", "body", "event"),
        created_tick=3,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="tool",
            binding_mode=ReplicationBindingMode.EXACT,
            exact_entity_id="item-a",
        ),
        operand_b_selector=None,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(),
    )
    ledger = empty_replication_ledger(OWNER)
    ledger, _ = append_replication_design(ledger, design)
    ledger, _ = adopt_replication_design(
        OWNER,
        ledger,
        design,
        delivery_event_id="delivery-1",
        received_tick=4,
        inviter_entity_id="body-a",
    )
    collaboration = ReplicationCollaboration(
        owner_id=OWNER,
        invitation_token=replication_ref("rinv", OWNER.value, "invite"),
        design_token=design.design_token,
        source_trial_token=design.source_trial_token,
        inviter_entity_id="body-a",
        created_tick=4,
        delivery_event_id="invite-delivery",
    )
    ledger, _ = open_replication_collaboration(ledger, collaboration)
    return ledger


def _experiment_ledger() -> object:
    return empty_experiment_ledger(
        OWNER,
        ExperimentCognitionBinding(2, 1, 2, False, False),
    )


def test_replication_state_round_trips_without_payload_loss() -> None:
    ledger = _ledger()
    payload = encode_replication_state(ledger)
    assert payload["version"] == REPLICATION_STATE_VERSION
    assert payload["owner_id"] == OWNER.value
    restored = decode_replication_state(payload, OWNER)
    assert restored == ledger
    assert replication_state_digest(restored) == replication_state_digest(ledger)


def test_scientific_experiment_state_round_trips() -> None:
    ledger = _experiment_ledger()
    payload = encode_scientific_experiment_state(ledger)
    restored = decode_scientific_experiment_state(payload, OWNER)
    assert restored == ledger
    assert scientific_experiment_state_digest(restored) == (
        scientific_experiment_state_digest(ledger)
    )


def test_foreign_owner_and_unsupported_versions_fail_closed() -> None:
    payload = encode_replication_state(_ledger())
    with pytest.raises(ReplicationCheckpointError):
        decode_replication_state(payload, OTHER)
    tampered = dict(payload)
    tampered["version"] = "replication-state-v9"
    with pytest.raises(ReplicationCheckpointError):
        decode_replication_state(tampered, OWNER)
    tampered = dict(payload)
    tampered["ledger"] = {"$type": "UnknownLedger"}
    with pytest.raises(ReplicationCheckpointError):
        decode_replication_state(tampered, OWNER)


def test_field_tampering_is_rejected_even_at_equal_counts() -> None:
    payload = encode_replication_state(_ledger())
    ledger = payload["ledger"]
    assert isinstance(ledger, dict)
    designs = ledger["designs"]
    assert isinstance(designs, list)
    designs[0]["created_tick"] = -1
    with pytest.raises(ReplicationCheckpointError):
        decode_replication_state(payload, OWNER)


@pytest.mark.asyncio
async def test_pending_v2_round_trips_candidates_and_v1_stays_unchanged() -> None:
    import dataclasses

    from simulation.models import RunId
    from simulation.run_control import (
        FINALIZATION_COMMAND_CODEC_VERSION,
        FINALIZATION_COMMAND_CODEC_VERSION_V2,
    )
    from simulation.runner_serialization import (
        decode_finalization_command,
        encode_finalization_command,
    )
    from tests.unit.test_runner_finalization import _obs, _runtime, _token

    runtime, _ = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    v1 = pending.to_finalization_command(run_id=RunId("run-v2-check"))
    assert v1.codec_version == FINALIZATION_COMMAND_CODEC_VERSION
    encoded_v1 = encode_finalization_command(v1)
    assert b"replication_state" not in encoded_v1
    assert b"scientific_experiment_state" not in encoded_v1
    decoded_v1 = decode_finalization_command(encoded_v1)
    assert decoded_v1.replication_ledger is None
    assert decoded_v1.experiment_ledger is None

    owner = pending.submission.agent_id
    ledger = empty_replication_ledger(owner)
    experiment = empty_experiment_ledger(
        owner, ExperimentCognitionBinding(2, 1, 2, False, False)
    )
    v2 = dataclasses.replace(
        v1,
        codec_version=FINALIZATION_COMMAND_CODEC_VERSION_V2,
        replication_ledger=ledger,
        experiment_ledger=experiment,
    )
    decoded = decode_finalization_command(encode_finalization_command(v2))
    assert decoded.codec_version == FINALIZATION_COMMAND_CODEC_VERSION_V2
    assert decoded.replication_ledger == ledger
    assert decoded.experiment_ledger == experiment
