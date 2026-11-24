# mypy: ignore-errors

"""v7 pending recovery, bind/finalize, and runtime checkpoint for commons."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.commons_governance import (
    CommonsLedger,
    empty_commons_ledger,
)
from agents.cognition.configuration import (
    CognitionFormalRuleMode,
    CognitionInstitutionConceptMode,
    CognitionLoopConfig,
    CognitionSocialNormMode,
    build_cognitive_loop,
    production_cognition_config,
)
from agents.cognition.models import InternalAgentState
from agents.models import Agent, AgentId
from memory.models import BeliefStore, MemoryStore
from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeErrorCode,
    _pending_integrity_hash,
    _v7_candidate_digest,
    pending_from_finalization_command,
)
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.lifecycle import ActionSubmission, TickToken
from simulation.models import RunId
from simulation.persistence import PENDING_FINALIZATION_ACCEPTED_VERSIONS
from simulation.run_control import (
    FINALIZATION_COMMAND_CODEC_VERSION_V6,
    FINALIZATION_COMMAND_CODEC_VERSION_V7,
    AgentRuntimeStatus,
    FinalizationCommand,
)
from simulation.runner_serialization import (
    decode_finalization_command,
    encode_finalization_command,
)
from tests.simulation_helpers import (
    alive_body,
    make_location,
    weather_for_locations,
)
from tests.unit.test_runner_finalization import _obs, _token
from world.actions import Drink, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation, observed_self_from_body
from world.values import ResourceKind, Thirst

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_ENTITY = EntityId("body-1")
_STOCK = EntityId("stock-a")


def _commons_loop() -> object:
    cfg = replace(
        production_cognition_config(),
        formal_rule_mode=CognitionFormalRuleMode.DETERMINISTIC,
        social_norm_mode=CognitionSocialNormMode.DETERMINISTIC,
        institution_concept_mode=CognitionInstitutionConceptMode.DETERMINISTIC,
    )
    assert type(cfg) is CognitionLoopConfig
    return build_cognitive_loop(
        cfg,
        commons_governance_stock_ids=(_STOCK,),
    )


def _runtime() -> tuple[AgentRuntime, MemoryStore]:
    locations = (make_location("loc-1", name="Camp"),)
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(body,),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(_OWNER, _ENTITY),),
    )
    memories = MemoryStore(_OWNER)
    beliefs = BeliefStore(_OWNER)
    runtime = AgentRuntime(
        agent=Agent(agent_id=_OWNER, name="agent-1", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=_commons_loop(),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    return runtime, memories


def _resource(quantity: float = 4.0) -> object:
    from world.observations import ObservedResource

    return ObservedResource(
        entity_id=_STOCK,
        name=_STOCK.value,
        kind=ResourceKind.WATER,
        quantity=quantity,
        unit="L",
    )


def _ledger(tick: int = 3) -> CommonsLedger:
    from agents.cognition.commons_governance import advance_commons_evidence

    body = alive_body("body-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=_ENTITY,
        revision=WorldRevision(tick),
        tick=tick,
        self_body=observed_self_from_body(body),
        resources=(_resource(),),
    )
    prior = empty_commons_ledger(_OWNER, _ENTITY)
    return advance_commons_evidence(_OWNER, prior, observation, (_STOCK,))


def _command(
    *,
    ledger: CommonsLedger | None = None,
    medical: object | None = None,
    integrity: str | None = None,
) -> FinalizationCommand:
    ledger = _ledger() if ledger is None else ledger
    token = TickToken(value="token-1", tick=Tick(3))
    command = FinalizationCommand(
        codec_version=FINALIZATION_COMMAND_CODEC_VERSION_V7,
        run_id=RunId("run-1"),
        agent_id=_OWNER,
        tick=3,
        invocation_id="inv-1",
        observation_key=(3, 0),
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
        submission=ActionSubmission(
            token=token, agent_id=_OWNER, command=Wait()
        ),
        subjective_batch=None,
        has_futures_boundary=False,
        final_confidence=0.5,
        medical_belief_ledger=medical,
        commons_governance_ledger=ledger,
    )
    expected = _pending_integrity_hash(
        invocation_id=command.invocation_id,
        tick=command.tick,
        command_kind=command.effective_command_kind,
        next_status=command.prior_status.value,
        revision_hint=0,
        candidate_digest=_v7_candidate_digest(command),
    )
    return replace(command, integrity_hash=integrity or expected)


def test_v7_is_in_pending_storage_allowlist() -> None:
    assert (
        FINALIZATION_COMMAND_CODEC_VERSION_V7
        in PENDING_FINALIZATION_ACCEPTED_VERSIONS
    )


def test_v7_round_trips_through_real_codec() -> None:
    command = _command()
    payload = encode_finalization_command(command)
    decoded = decode_finalization_command(payload)
    assert decoded == command
    assert decoded.commons_governance_ledger == _ledger()
    assert decoded.medical_belief_ledger is None


def test_v7_with_medical_round_trips() -> None:
    from agents.cognition.medical_beliefs import MedicalBeliefLedger, advance

    medical = advance(
        MedicalBeliefLedger(owner_id=_OWNER, observer_entity_id=_ENTITY),
        Observation(
            world_id=WorldId("world-1"),
            observer_id=_ENTITY,
            revision=WorldRevision(3),
            tick=3,
            self_body=observed_self_from_body(alive_body("body-1")),
        ),
    )
    command = _command(medical=medical)
    decoded = decode_finalization_command(encode_finalization_command(command))
    assert decoded.medical_belief_ledger == medical
    assert decoded.commons_governance_ledger == _ledger()


def test_v7_requires_commons_and_legacy_forbids_it() -> None:
    from agents.cognition.medical_beliefs import MedicalBeliefLedger, advance

    command = _command()
    fields = {
        field.name: getattr(command, field.name)
        for field in command.__dataclass_fields__.values()
    }
    with pytest.raises(ValueError, match="v7_requires_commons_governance_payload"):
        FinalizationCommand(**{**fields, "commons_governance_ledger": None})
    medical = advance(
        MedicalBeliefLedger(owner_id=_OWNER, observer_entity_id=_ENTITY),
        Observation(
            world_id=WorldId("world-1"),
            observer_id=_ENTITY,
            revision=WorldRevision(3),
            tick=3,
            self_body=observed_self_from_body(alive_body("body-1")),
        ),
    )
    with pytest.raises(ValueError, match="legacy_forbids_commons_governance_payload"):
        FinalizationCommand(
            **{
                **fields,
                "codec_version": FINALIZATION_COMMAND_CODEC_VERSION_V6,
                "medical_belief_ledger": medical,
            }
        )


def test_v1_through_v6_bytes_unchanged_without_commons_key() -> None:
    from agents.cognition.medical_beliefs import MedicalBeliefLedger, advance
    from simulation.agent_runtime import _v6_candidate_digest

    medical = advance(
        MedicalBeliefLedger(owner_id=_OWNER, observer_entity_id=_ENTITY),
        Observation(
            world_id=WorldId("world-1"),
            observer_id=_ENTITY,
            revision=WorldRevision(3),
            tick=3,
            self_body=observed_self_from_body(alive_body("body-1")),
        ),
    )
    token = TickToken(value="token-1", tick=Tick(3))
    v6 = FinalizationCommand(
        codec_version=FINALIZATION_COMMAND_CODEC_VERSION_V6,
        run_id=RunId("run-1"),
        agent_id=_OWNER,
        tick=3,
        invocation_id="inv-1",
        observation_key=(3, 0),
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
        submission=ActionSubmission(
            token=token, agent_id=_OWNER, command=Wait()
        ),
        subjective_batch=None,
        has_futures_boundary=False,
        final_confidence=0.5,
        medical_belief_ledger=medical,
    )
    expected = _pending_integrity_hash(
        invocation_id=v6.invocation_id,
        tick=v6.tick,
        command_kind=v6.effective_command_kind,
        next_status=v6.prior_status.value,
        revision_hint=0,
        candidate_digest=_v6_candidate_digest(v6),
    )
    v6 = replace(v6, integrity_hash=expected)
    mapping = __import__(
        "simulation.runner_serialization", fromlist=["finalization_command_to_mapping"]
    ).finalization_command_to_mapping(v6)
    assert "commons_governance_state" not in mapping
    assert set(mapping) >= {
        "medical_beliefs_state",
        "replication_state",
        "scientific_experiment_state",
        "measurement_state",
        "scientific_model_state",
        "competing_theory_state",
    }


def test_pending_reconstruction_preserves_commons_candidate() -> None:
    pending = pending_from_finalization_command(_command())
    assert pending.loop_result.commons_governance_ledger == _ledger()


def test_restore_accepts_verified_v7_and_rejects_tampered_candidate() -> None:
    runtime, _ = _runtime()
    command = _command()
    pending = runtime.restore_pending_from_command(command)
    assert pending.loop_result.commons_governance_ledger == _ledger()

    tampered_runtime, _ = _runtime()
    tampered = replace(_ledger(), omission_count=7)
    bad = _command(ledger=tampered, integrity=command.integrity_hash)
    with pytest.raises(AgentRuntimeError) as excinfo:
        tampered_runtime.restore_pending_from_command(bad)
    assert excinfo.value.code is AgentRuntimeErrorCode.RECOVERY_CORRUPT
    assert tampered_runtime._pending is None


def test_runtime_checkpoint_exports_and_restores_commons_ledger() -> None:
    runtime, _ = _runtime()
    runtime._loop.restore_commons_governance_ledger(_ledger(), _OWNER)
    checkpoint = runtime.export_runtime_checkpoint()
    assert checkpoint.commons_governance_ledger == _ledger()

    restored, _ = _runtime()
    restored.restore_runtime_checkpoint(checkpoint)
    assert restored._loop.commons_governance_ledger_if_present() == _ledger()
    assert restored._loop._commons_governance_enabled() is True


def test_candidate_digest_changes_with_commons_state() -> None:
    base = _command()
    other = _command(
        ledger=replace(_ledger(), omission_count=2),
        integrity=base.integrity_hash,
    )
    assert _v7_candidate_digest(base) != _v7_candidate_digest(other)


@pytest.mark.asyncio
async def test_prepare_bind_commit_installs_immutable_candidate() -> None:
    runtime, _ = _runtime()
    runtime.start()
    body = alive_body("body-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=_ENTITY,
        revision=WorldRevision(0),
        tick=0,
        self_body=observed_self_from_body(body),
        resources=(_resource(),),
    )
    prepared = await runtime.prepare_observation(observation, token=_token(0))
    assert prepared.proposal.commons_governance_ledger is not None
    pending = await runtime.bind_effective_command(prepared)
    assert pending.loop_result.commons_governance_ledger is not None
    assert pending.submission.command == pending.loop_result.command
    assert (
        pending.effective_command_kind
        == type(pending.loop_result.command).__name__.lower()
    )
    command = pending.to_finalization_command(run_id=RunId("run-commons-v7"))
    assert command.codec_version == FINALIZATION_COMMAND_CODEC_VERSION_V7
    await runtime.finalize_pending(pending)
    committed = runtime._loop.commons_governance_ledger_if_present()
    assert type(committed) is CommonsLedger
    assert committed.last_processed_tick == 0


@pytest.mark.asyncio
async def test_override_preserves_evidence_without_command_adaptation() -> None:
    runtime, _ = _runtime()
    runtime.start()
    body = replace(alive_body("body-1"), thirst=Thirst(0.2))
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=_ENTITY,
        revision=WorldRevision(1),
        tick=1,
        self_body=observed_self_from_body(body),
        resources=(_resource(3.5),),
    )
    prepared = await runtime.prepare_observation(observation, token=_token(1))
    drink = Drink(source_id=_STOCK)
    pending = await runtime.bind_effective_command(
        prepared, effective_command=drink
    )
    assert type(pending.submission.command) is Drink
    await runtime.finalize_pending(pending)
    ledger = runtime._loop.commons_governance_ledger_if_present()
    assert type(ledger) is CommonsLedger
    assert ledger.last_processed_tick == 1


@pytest.mark.asyncio
async def test_abort_then_retry_does_not_duplicate_owner_effects() -> None:
    runtime, _ = _runtime()
    runtime.start()
    body = alive_body("body-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=_ENTITY,
        revision=WorldRevision(0),
        tick=0,
        self_body=observed_self_from_body(body),
        resources=(_resource(),),
    )
    prepared = await runtime.prepare_observation(observation, token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    runtime.abort_pending(pending)
    assert runtime._loop.commons_governance_ledger_if_present() is None

    prepared = await runtime.prepare_observation(observation, token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    await runtime.finalize_pending(pending)
    ledger = runtime._loop.commons_governance_ledger_if_present()
    assert ledger is not None
    assert ledger.last_processed_tick == 0


@pytest.mark.asyncio
async def test_missing_checkpoint_ledger_after_processing_is_rejected() -> None:
    runtime, _ = _runtime()
    runtime.start()
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=_ENTITY,
        revision=WorldRevision(0),
        tick=0,
        self_body=observed_self_from_body(alive_body("body-1")),
        resources=(_resource(),),
    )
    prepared = await runtime.prepare_observation(observation, token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    await runtime.finalize_pending(pending)
    checkpoint = runtime.export_runtime_checkpoint()
    assert checkpoint.processed_invocation_count > 0
    stripped = replace(checkpoint, commons_governance_ledger=None)

    restored, _ = _runtime()
    with pytest.raises(AgentRuntimeError) as excinfo:
        restored.restore_runtime_checkpoint(stripped)
    assert excinfo.value.code is AgentRuntimeErrorCode.OWNERSHIP


@pytest.mark.asyncio
async def test_export_commons_governance_ledgers_finalized_only() -> None:
    from dataclasses import replace as _replace

    from simulation.runner import RunnerDependencyFactories, SimulationRunner
    from tests.unit.test_commons_governance_config import _as_v62, _ecology_base

    config = _as_v62(_ecology_base())
    runner = await SimulationRunner.from_config(
        _replace(config, stop_policy=_replace(config.stop_policy, max_ticks=2)),
        run_id=RunId("run-commons-export"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        export_before = runner.export_commons_governance_ledgers()
        assert export_before.expected_count >= 1
        assert len(export_before.ledgers) == 0
        assert len(export_before.unavailable_owner_ids) == export_before.expected_count
        await runner.run_tick()
        export_after = runner.export_commons_governance_ledgers()
        assert (
            len(export_after.ledgers) + len(export_after.unavailable_owner_ids)
            == export_after.expected_count
        )


@pytest.mark.asyncio
async def test_unqualified_entrant_gets_no_mutable_commons_state() -> None:
    from agents.cognition.defaults import default_cognitive_loop

    locations = (make_location("loc-1", name="Camp"),)
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(alive_body("body-1"),),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(_OWNER, _ENTITY),),
    )
    memories = MemoryStore(_OWNER)
    beliefs = BeliefStore(_OWNER)
    loop = default_cognitive_loop()
    loop.bind_commons_governance((_STOCK,))
    assert loop._commons_governance_enabled() is False
    runtime = AgentRuntime(
        agent=Agent(agent_id=_OWNER, name="agent-1", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=loop,
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=0), token=_token(0))
    assert prepared.proposal.commons_governance_ledger is None
    pending = await runtime.bind_effective_command(prepared)
    assert pending.loop_result.commons_governance_ledger is None
    assert (
        pending.to_finalization_command(run_id=RunId("run-unqualified")).codec_version
        != FINALIZATION_COMMAND_CODEC_VERSION_V7
    )
