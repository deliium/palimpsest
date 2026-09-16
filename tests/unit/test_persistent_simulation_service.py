"""PersistentSimulationService prepare/persist/finalize contracts."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import EnginePhase, WorldEngine
from simulation.journal import compute_commit_hash, hash_tick_events, hash_tick_payload
from simulation.lifecycle import (
    ActionSubmission,
    EngineDiagnosticCode,
)
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    TickAppendRequest,
    TickCommit,
)
from simulation.service import DurableCommitAmbiguity, PersistentSimulationService
from world.actions import Wait
from world.events import WorldEvent
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst


def _alive(entity_id: str = "body-1") -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
    )


def _engine(*, seed: int = 11) -> WorldEngine:
    return WorldEngine(
        config=SimulationRunConfig(seed=seed),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
            bodies=(_alive(),),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            ),
        ),
        run_id=RunId("run-durable-1"),
    )


def _commit_for(request: TickAppendRequest) -> TickCommit:
    payload = hash_tick_payload(request.events)
    event_hashes = hash_tick_events(request.events)
    resulting_revision = (
        request.events[-1].resulting_revision
        if request.events
        else request.expected_base_revision
    )
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        run_id=request.run_id,
        tick=request.tick,
        base_revision=request.expected_base_revision,
        resulting_revision=resulting_revision,
        event_hashes=event_hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=request.run_id,
        tick=request.tick,
        resulting_tick=Tick(request.tick.value + 1),
        base_revision=request.expected_base_revision,
        resulting_revision=resulting_revision,
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        commit_hash=commit_hash,
        idempotency_key=request.idempotency_key,
        event_count=len(request.events),
        payload_hash=payload,
        snapshot_id=None if request.snapshot is None else request.snapshot.snapshot_id,
    )


class _FakeJournal:
    def __init__(self) -> None:
        self.commits: dict[tuple[str, int], TickCommit] = {}
        self.fail_with: BaseException | None = None
        self.calls = 0

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        self.calls += 1
        if self.fail_with is not None:
            raise self.fail_with
        key = (request.run_id.value, request.tick.value)
        existing = self.commits.get(key)
        built = _commit_for(request)
        if existing is not None:
            if existing.commit_hash != built.commit_hash:
                raise ValueError("divergent idempotent reuse")
            return existing
        self.commits[key] = built
        return built

    async def get_tick_commit(
        self, run_id: RunId, tick: Tick
    ) -> TickCommit | None:
        return self.commits.get((run_id.value, tick.value))

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        _ = (run_id, from_tick, to_tick, limit, offset)
        return ()

    async def list_tick_commits(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
    ) -> tuple[TickCommit, ...]:
        selected = [
            commit
            for (run_value, tick_value), commit in self.commits.items()
            if run_value == run_id.value
            and tick_value >= from_tick.value
            and (to_tick is None or tick_value <= to_tick.value)
        ]
        return tuple(sorted(selected, key=lambda item: item.tick.value))


@pytest.mark.asyncio
async def test_durable_empty_tick_persists_then_finalizes() -> None:
    engine = _engine()
    engine.observe()
    journal = _FakeJournal()
    service = PersistentSimulationService(engine, journal)
    commit = await service.resolve_tick(())
    assert commit.event_count == 0
    assert commit.tick == Tick(0)
    assert engine.tick == Tick(1)
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    assert service.predecessor_commit_hash == commit.commit_hash
    assert journal.calls == 1


@pytest.mark.asyncio
async def test_durable_event_only_tick_persists_events() -> None:
    engine = _engine()
    batch = engine.observe()
    journal = _FakeJournal()
    service = PersistentSimulationService(engine, journal)
    commit = await service.resolve_tick(
        (
            ActionSubmission(
                agent_id=AgentId("agent-1"),
                command=Wait(),
                token=batch.token,
            ),
        )
    )
    assert commit.event_count == 1
    assert engine.tick == Tick(1)
    assert engine.revision == WorldRevision(0)
    stored = await journal.get_tick_commit(engine.run_id, Tick(0))
    assert stored is not None
    assert stored.commit_hash == commit.commit_hash


@pytest.mark.asyncio
async def test_adapter_failure_leaves_engine_unchanged() -> None:
    engine = _engine()
    batch = engine.observe()
    journal = _FakeJournal()
    journal.fail_with = RuntimeError("db down")
    service = PersistentSimulationService(engine, journal)
    before_tick = engine.tick
    before_phase = engine.phase
    before_revision = engine.revision
    with pytest.raises(RuntimeError, match="db down"):
        await service.resolve_tick(
            (
                ActionSubmission(
                    agent_id=AgentId("agent-1"),
                    command=Wait(),
                    token=batch.token,
                ),
            )
        )
    assert engine.tick == before_tick
    assert engine.phase is before_phase
    assert engine.revision == before_revision
    assert service.fenced is False
    assert service.predecessor_commit_hash is None


@pytest.mark.asyncio
async def test_ambiguous_commit_fences_without_finalize() -> None:
    engine = _engine()
    engine.observe()
    journal = _FakeJournal()
    journal.fail_with = DurableCommitAmbiguity("unknown outcome")
    service = PersistentSimulationService(engine, journal)
    with pytest.raises(DurableCommitAmbiguity):
        await service.resolve_tick(())
    assert engine.tick == Tick(0)
    assert engine.phase is EnginePhase.AWAITING_SUBMISSIONS
    assert service.fenced is True
    with pytest.raises(RuntimeError, match="fenced"):
        await service.resolve_tick(())


@pytest.mark.asyncio
async def test_idempotent_retry_warns_and_finalizes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine()
    engine.observe()
    journal = _FakeJournal()
    service = PersistentSimulationService(engine, journal)
    first = await service.resolve_tick((), idempotency_key="idem-tick-0")
    # Simulate crash-window retry against a fresh engine that has not finalized:
    engine2 = _engine()
    engine2.observe()
    service2 = PersistentSimulationService(engine2, journal)
    with caplog.at_level(logging.WARNING, logger="simulation.service"):
        second = await service2.resolve_tick((), idempotency_key="idem-tick-0")
    assert second.commit_hash == first.commit_hash
    assert EngineDiagnosticCode.DURABLE_IDEMPOTENT.value in " ".join(
        record.getMessage() for record in caplog.records
    )
    assert engine2.tick == Tick(1)


@pytest.mark.asyncio
async def test_prepared_candidate_not_public() -> None:
    import simulation

    assert "_PreparedTickCandidate" not in simulation.__all__
    assert not hasattr(simulation, "_PreparedTickCandidate")


@pytest.mark.asyncio
async def test_in_memory_resolve_tick_still_works() -> None:
    engine = _engine()
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                agent_id=AgentId("agent-1"),
                command=Wait(),
                token=batch.token,
            ),
        )
    )
    assert result.tick == Tick(0)
    assert engine.tick == Tick(1)


@pytest.mark.asyncio
async def test_durable_logs_omit_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _engine(seed=2**70 + 3)
    batch = engine.observe()
    journal = _FakeJournal()
    service = PersistentSimulationService(engine, journal)
    with caplog.at_level(logging.DEBUG, logger="simulation.service"):
        await service.resolve_tick(
            (
                ActionSubmission(
                    agent_id=AgentId("agent-1"),
                    command=Wait(),
                    token=batch.token,
                ),
            )
        )
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert EngineDiagnosticCode.DURABLE_COMMITTED.value in joined
    assert "Camp" not in joined
    assert "Wait" not in joined
    assert str(engine._config.seed) not in joined
