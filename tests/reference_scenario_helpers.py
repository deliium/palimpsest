"""Shared helpers for reference-scenario unit tests (metadata-only assertions)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from agents.models import AgentId
from experiments.reference_scenario import (
    AGENT_KAI,
    AGENT_MIRA,
    AGENT_NYX,
    AGENT_ROWAN,
    AGENT_SOREN,
    REFERENCE_DEATH_TICK,
    REFERENCE_DEFAULT_OVERRIDE_BUDGET,
    REFERENCE_MAX_TICKS,
    REFERENCE_SCENARIO_ID,
    REFERENCE_SCENARIO_VERSION,
    ReferenceScenarioBundle,
    build_reference_scenario,
)
from memory.models import MemoryScope, MemorySourceKind, MemoryTrace
from memory.service import InMemoryMemoryService
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import SimulationRunnerResult
from simulation.runner_serialization import build_runner_result_document
from social.relationships import DirectedRelationshipProfile
from social.service import InMemoryRelationshipService
from world.models import DayPhase

REFERENCE_AGENT_IDS: tuple[str, ...] = (
    AGENT_MIRA,
    AGENT_KAI,
    AGENT_ROWAN,
    AGENT_SOREN,
    AGENT_NYX,
)

OWNED_LOGGER_PREFIXES: Final[tuple[str, ...]] = (
    "simulation.",
    "experiments.",
    "agents.cognition.",
    "memory.",
    "social.",
    "analysis.",
    "api.",
    "infrastructure.",
    "persistence.",
    "world.",
    "llm.",
)

_FORBIDDEN_LOG_FRAGMENTS: Final[tuple[str, ...]] = (
    "spring-holds-water",
    "secure-food",
    "sk-",
    "password",
    "secret",
    "Bearer ",
    "postgres://",
    "postgresql://",
)


def make_reference_bundle(
    *,
    override_budget: int = REFERENCE_DEFAULT_OVERRIDE_BUDGET,
    death_tick: int = REFERENCE_DEATH_TICK,
    max_ticks: int = REFERENCE_MAX_TICKS,
    seed: int | None = None,
) -> ReferenceScenarioBundle:
    """Build the canonical reference scenario for unit assertions."""
    if seed is None:
        return build_reference_scenario(
            override_budget=override_budget,
            death_tick=death_tick,
            max_ticks=max_ticks,
        )
    return build_reference_scenario(
        seed=seed,
        override_budget=override_budget,
        death_tick=death_tick,
        max_ticks=max_ticks,
    )


def assert_reference_shape(bundle: ReferenceScenarioBundle) -> None:
    """Assert public scenario shape without inspecting payload content."""
    assert bundle.scenario_id == REFERENCE_SCENARIO_ID
    assert bundle.scenario_version == REFERENCE_SCENARIO_VERSION
    assert bundle.config.stop_policy.max_ticks == REFERENCE_MAX_TICKS or (
        bundle.config.stop_policy.max_ticks >= 1
    )
    assert len(bundle.config.agents) == 5
    assert {agent.agent_id.value for agent in bundle.config.agents} == set(
        REFERENCE_AGENT_IDS
    )
    assert len(bundle.config.scenario.locations) >= 2
    assert len(bundle.config.scenario.resources) >= 2
    assert bundle.death_tick <= bundle.config.stop_policy.max_ticks // 2
    assert bundle.override_budget == bundle.arbiter.override_budget
    assert len(bundle.milestone_ids) >= 1
    assert len(bundle.milestone_ids) <= bundle.override_budget


@dataclass
class SubjectiveEvidenceCapture:
    """Retains public in-memory subjective services for post-run inspection."""

    memories: dict[str, InMemoryMemoryService] = field(default_factory=dict)
    relationships: dict[str, InMemoryRelationshipService] = field(default_factory=dict)

    def factories(self) -> RunnerDependencyFactories:
        capture = self

        def memory_factory(
            scope: MemoryScope, *, reconstructor: object | None = None
        ) -> InMemoryMemoryService:
            service = InMemoryMemoryService(scope, reconstructor=reconstructor)
            capture.memories[scope.owner_id.value] = service
            return service

        def relationship_factory(owner_id: AgentId) -> InMemoryRelationshipService:
            service = InMemoryRelationshipService(owner_id)
            capture.relationships[owner_id.value] = service
            return service

        return RunnerDependencyFactories(
            memory_factory=memory_factory,
            relationship_factory=relationship_factory,
        )


@dataclass(frozen=True, slots=True)
class ReferenceRunOutcome:
    """Public receipts plus captured subjective evidence for invariant proofs."""

    bundle: ReferenceScenarioBundle
    result: SimulationRunnerResult
    runtime_statuses: Mapping[str, str]
    memories: Mapping[str, tuple[MemoryTrace, ...]]
    relationships: Mapping[str, tuple[DirectedRelationshipProfile, ...]]
    terminal_at_n_plus_one: Mapping[str, bool]


async def run_reference_scenario(
    *,
    run_id: str = "run-reference-e2e",
    seed: int | None = None,
    max_ticks: int | None = None,
    death_tick: int | None = None,
) -> ReferenceRunOutcome:
    """Run the five-agent scenario through production in-memory architecture.

    Uses public runner APIs only. Does not read the live engine handle,
    private world authority modules, or WorldState.
    """
    if seed is None and max_ticks is None and death_tick is None:
        bundle = build_reference_scenario()
    else:
        bundle = build_reference_scenario(
            **{
                key: value
                for key, value in {
                    "seed": seed,
                    "max_ticks": max_ticks,
                    "death_tick": death_tick,
                }.items()
                if value is not None
            }
        )
    capture = SubjectiveEvidenceCapture()
    death = bundle.death_tick
    death_agent = bundle.death_agent_id.value
    terminal_at_n_plus_one: dict[str, bool] = {}

    async with await SimulationRunner.from_config(
        bundle.config,
        run_id=RunId(run_id),
        factories=capture.factories(),
    ) as runner:
        runner.set_intervention_arbiter(bundle.arbiter)
        result = await runner.run()
        runtime_statuses = {
            runtime.agent_id.value: runtime.status.value for runtime in runner.runtimes
        }

    # N+1 terminal: victim has no applied action at death+1 and ends TERMINAL.
    n1_applied = [
        resolution
        for receipt in result.finalized_tick_receipts
        if receipt.tick == death + 1
        for resolution in receipt.resolutions
        if resolution.agent_id.value == death_agent
        and resolution.status.value == "applied"
    ]
    terminal_at_n_plus_one = {
        death_agent: (
            runtime_statuses.get(death_agent) == AgentRuntimeStatus.TERMINAL.value
            and n1_applied == []
        )
    }

    memories = {
        owner: await service.snapshot() for owner, service in capture.memories.items()
    }
    relationships = {
        owner: await service.snapshot()
        for owner, service in capture.relationships.items()
    }
    return ReferenceRunOutcome(
        bundle=bundle,
        result=result,
        runtime_statuses=runtime_statuses,
        memories=memories,
        relationships=relationships,
        terminal_at_n_plus_one=terminal_at_n_plus_one,
    )


def day_night_phases(bundle: ReferenceScenarioBundle) -> set[DayPhase]:
    """Phases covered by the configured tick window (public rules only)."""
    rules = bundle.config.resolve_physical_rules()
    return {
        rules.day_phase_for_tick(tick)
        for tick in range(bundle.config.stop_policy.max_ticks)
    }


def applied_command_kinds(result: SimulationRunnerResult) -> dict[str, int]:
    counts: dict[str, int] = {}
    for receipt in result.finalized_tick_receipts:
        for resolution in receipt.resolutions:
            if resolution.status.value != "applied":
                continue
            counts[resolution.command_kind] = counts.get(resolution.command_kind, 0) + 1
    return counts


def agent_resolutions_after(
    result: SimulationRunnerResult, *, agent_id: str, after_tick: int
) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    for receipt in result.finalized_tick_receipts:
        for resolution in receipt.resolutions:
            if resolution.agent_id.value != agent_id:
                continue
            if resolution.tick <= after_tick:
                continue
            rows.append(
                (resolution.tick, resolution.command_kind, resolution.status.value)
            )
    return rows


def assert_owned_logs_privacy_safe(records: Sequence[logging.LogRecord]) -> None:
    """Reject payloads/secrets; allow IDs, templates, cursors, versions, counts."""
    owned = [
        record
        for record in records
        if any(record.name.startswith(prefix) for prefix in OWNED_LOGGER_PREFIXES)
        or record.name in {prefix.rstrip(".") for prefix in OWNED_LOGGER_PREFIXES}
    ]
    for record in owned:
        text = record.getMessage()
        for fragment in _FORBIDDEN_LOG_FRAGMENTS:
            assert fragment not in text, f"forbidden log fragment in {record.name}"
        for key in ("cognition", "runtime", "memory", "analysis", "api"):
            payload = record.__dict__.get(key)
            if isinstance(payload, Mapping):
                blob = " ".join(str(value) for value in payload.values())
                for fragment in _FORBIDDEN_LOG_FRAGMENTS:
                    assert fragment not in blob


def result_document_hashes(
    result: SimulationRunnerResult, bundle: ReferenceScenarioBundle
) -> tuple[str, str]:
    document = build_runner_result_document(result=result, config=bundle.config)
    return document.exact_trajectory_hash, document.replica_normalized_trajectory_hash


def memory_kind_counts(
    memories: Mapping[str, tuple[MemoryTrace, ...]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for traces in memories.values():
        for trace in traces:
            kind = trace.provenance.kind.value
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def has_asymmetric_relationships(
    relationships: Mapping[str, tuple[DirectedRelationshipProfile, ...]],
) -> bool:
    """True when directed edges are not a perfect undirected mirror.

    Counts missing reciprocals, unequal dimension maps, or distinct
    relationship identities for opposite directions.
    """
    edges: dict[tuple[str, str], tuple[str, dict[str, float]]] = {}
    for owner, profiles in relationships.items():
        for profile in profiles:
            dims = {
                item.dimension.value: float(getattr(item.value, "value", item.value))
                for item in profile.dimensions
            }
            edges[(owner, profile.target_id.value)] = (
                profile.relationship_id.value,
                dims,
            )
    if not edges:
        return False
    for (source, target), (relationship_id, dims) in edges.items():
        reciprocal = edges.get((target, source))
        if reciprocal is None:
            return True
        other_id, other_dims = reciprocal
        if other_id == relationship_id:
            return True
        if other_dims != dims:
            return True
        # Opposite directions always use distinct relationship ids → asymmetric.
        if other_id != relationship_id:
            return True
    return False


def reconstructed_trace_count(
    memories: Mapping[str, tuple[MemoryTrace, ...]],
) -> int:
    """Count traces whose public lineage names a reconstruction id."""
    total = 0
    for traces in memories.values():
        for trace in traces:
            if (
                trace.lineage is not None
                and trace.lineage.reconstruction_id is not None
            ):
                total += 1
    return total


def direct_trace_count(memories: Mapping[str, tuple[MemoryTrace, ...]]) -> int:
    total = 0
    for traces in memories.values():
        for trace in traces:
            if trace.provenance.kind is MemorySourceKind.DIRECT_OBSERVATION and (
                trace.lineage is None or trace.lineage.reconstruction_id is None
            ):
                total += 1
    return total


def communicated_trace_count(
    memories: Mapping[str, tuple[MemoryTrace, ...]],
) -> int:
    return sum(
        1
        for traces in memories.values()
        for trace in traces
        if trace.provenance.kind is MemorySourceKind.COMMUNICATED
    )
