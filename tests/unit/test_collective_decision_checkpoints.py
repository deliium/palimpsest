"""Collective-decision runtime checkpoint continuation (not durable restart)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V51,
    CollectiveDecisionMode,
    InstitutionConceptMode,
)


def _config(max_ticks: int = 6, *, enabled: bool = True):
    definition = institutionalization_scenario(seed=23, max_ticks=max_ticks)
    base = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-baseline"
    )
    if not enabled:
        return base
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V51,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    institution_concept_mode=InstitutionConceptMode.DISABLED,
                    collective_decision_mode=CollectiveDecisionMode.DETERMINISTIC,
                ),
            )
            for agent in base.agents
        ),
    )


@pytest.mark.asyncio
async def test_runtime_checkpoint_preserves_enabled_owner_ledgers() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decisions-ckpt")
    ) as runner:
        await runner.run_tick()
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        before = runner.export_collective_decision_ledgers()

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decisions-ckpt")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        after = restored.export_collective_decision_ledgers()

    assert after == before
    assert len(after) == len(config.agents)
    assert all(
        state.collective_decisions is not None for state in checkpoint.runtime_states
    )


@pytest.mark.asyncio
async def test_restored_continuation_matches_uninterrupted_state() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decisions-continuation")
    ) as runner:
        await runner.run_tick()
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        for _ in range(4):
            await runner.run_tick()
        uninterrupted = runner.export_collective_decision_ledgers()

    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decisions-continuation")
    ) as restored:
        restored.apply_runtime_checkpoint(checkpoint)
        for _ in range(4):
            await restored.run_tick()
        restored_final = restored.export_collective_decision_ledgers()

    assert restored_final == uninterrupted


@pytest.mark.asyncio
async def test_forks_detach_decision_values() -> None:
    config = _config(max_ticks=4)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decisions-fork")
    ) as runner:
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        left_ledgers = runner.export_collective_decision_ledgers()

    async with (
        await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-fork")
        ) as left,
        await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-fork")
        ) as right,
    ):
        left.apply_runtime_checkpoint(checkpoint)
        right.apply_runtime_checkpoint(checkpoint)
        assert left.export_collective_decision_ledgers() == left_ledgers
        assert right.export_collective_decision_ledgers() == left_ledgers
        for _ in range(3):
            await left.run_tick()
            await right.run_tick()
        assert (
            left.export_collective_decision_ledgers()
            == right.export_collective_decision_ledgers()
        )


@pytest.mark.asyncio
async def test_disabled_owners_export_nothing() -> None:
    config = _config(enabled=False)
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decisions-off")
    ) as runner:
        await runner.run_tick()
        assert runner.export_collective_decision_ledgers() == ()


def _synthetic_ledger(owner, *, window_last: int = 1):
    from agents.cognition.collective_decisions import (
        CollectiveDecisionLedger,
        CollectiveEvidence,
        CollectiveEvidenceChannel,
        CollectiveProposal,
        CollectiveTopic,
        collective_decision_evidence_id,
        collective_proposal_id,
        collective_proposal_ref,
    )

    ref = collective_proposal_ref(
        owner,
        originator_id=None,
        topic=CollectiveTopic.COLLECTIVE_PROJECT,
        context_key="a" * 16,
        inception_tick=0,
        inception_lineage="checkpoint",
    )
    evidence = CollectiveEvidence(
        evidence_id=collective_decision_evidence_id(
            ref, 0, CollectiveEvidenceChannel.OBSERVED, "lineage"
        ),
        ordinal=0,
        channel=CollectiveEvidenceChannel.OBSERVED,
        lineage_ref="lineage",
        root_ref="root",
        tick=0,
    )
    return CollectiveDecisionLedger(
        owner_id=owner,
        proposals=(
            CollectiveProposal(
                proposal_id=collective_proposal_id(owner, ref, 0),
                owner_id=owner,
                proposal_ref=ref,
                revision=0,
                topic=CollectiveTopic.COLLECTIVE_PROJECT,
                context_key="a" * 16,
                action_token="start_project",
                first_tick=0,
                last_tick=0,
                window_first_tick=0,
                window_last_tick=window_last,
                evidence=(evidence,),
            ),
        ),
        first_observed_tick=0,
        last_observed_tick=0,
        observation_count=1,
    )


def test_foreign_collective_owner_in_checkpoint_rejects() -> None:
    from dataclasses import replace as dataclass_replace

    from agents.models import AgentId

    config = _config()

    async def capture():
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-foreign")
        ) as runner:
            await runner.run_tick()
            return runner.export_runtime_checkpoint()

    import asyncio

    checkpoint = asyncio.run(capture())
    states = list(checkpoint.runtime_states)
    foreign = _synthetic_ledger(AgentId("stranger"))
    import pytest as _pytest

    with _pytest.raises(ValueError, match="owner_id mismatch"):
        states[0] = dataclass_replace(states[0], collective_decisions=foreign)


def test_duplicate_runtime_owner_in_checkpoint_rejects() -> None:
    from dataclasses import replace as dataclass_replace

    config = _config()

    async def capture():
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-duplicate")
        ) as runner:
            await runner.run_tick()
            return runner.export_runtime_checkpoint()

    import asyncio

    checkpoint = asyncio.run(capture())
    states = list(checkpoint.runtime_states)
    states[-1] = states[0]
    bad = dataclass_replace(checkpoint, runtime_states=tuple(states))

    async def restore():
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-duplicate")
        ) as runner:
            runner.apply_runtime_checkpoint(bad)

    import pytest as _pytest

    with _pytest.raises(ValueError, match="duplicate runtime state owner"):
        asyncio.run(restore())


def test_reapplying_checkpoint_is_idempotent() -> None:
    config = _config()

    async def run():
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-retry")
        ) as runner:
            await runner.run_tick()
            checkpoint = runner.export_runtime_checkpoint()
            runner.apply_runtime_checkpoint(checkpoint)
            first = runner.export_collective_decision_ledgers()
            runner.apply_runtime_checkpoint(checkpoint)
            second = runner.export_collective_decision_ledgers()
            return first, second

    import asyncio

    first, second = asyncio.run(run())
    assert first == second


def test_expiry_survives_restore() -> None:
    from dataclasses import replace as dataclass_replace

    config = _config(max_ticks=4)

    async def run():
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-expiry")
        ) as runner:
            await runner.run_tick()
            await runner.run_tick()
            checkpoint = runner.export_runtime_checkpoint()
            states = list(checkpoint.runtime_states)
            states[0] = dataclass_replace(
                states[0],
                collective_decisions=_synthetic_ledger(
                    states[0].agent_id, window_last=1
                ),
            )
            seeded = dataclass_replace(checkpoint, runtime_states=tuple(states))
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-expiry")
        ) as runner:
            runner.apply_runtime_checkpoint(seeded)
            await runner.run_tick()
            return runner.export_collective_decision_ledgers()

    import asyncio

    ledgers = asyncio.run(run())
    assert ledgers[0].proposals[0].status.value == "expired"


def test_terminal_actor_checkpoint_keeps_ledger_without_confirmation() -> None:
    from dataclasses import replace as dataclass_replace

    from simulation.agent_runtime import AgentRuntimeStatus

    config = _config(max_ticks=4)

    async def run():
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-terminal")
        ) as runner:
            await runner.run_tick()
            checkpoint = runner.export_runtime_checkpoint()
            states = list(checkpoint.runtime_states)
            seeded = _synthetic_ledger(states[0].agent_id, window_last=8)
            states[0] = dataclass_replace(
                states[0],
                status=AgentRuntimeStatus.TERMINAL,
                collective_decisions=seeded,
            )
            terminal = dataclass_replace(checkpoint, runtime_states=tuple(states))
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-decisions-terminal")
        ) as runner:
            runner.apply_runtime_checkpoint(terminal)
            await runner.run_tick()
            return runner.export_collective_decision_ledgers()

    import asyncio

    ledgers = asyncio.run(run())
    terminal_ledger = next(
        ledger for ledger in ledgers if ledger.owner_id.value == "agent-a"
    )
    assert len(terminal_ledger.proposals) == 1
    assert terminal_ledger.compliance == ()
