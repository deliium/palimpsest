"""Unit proofs for research branch identity helpers."""

from __future__ import annotations

from simulation.branching import (
    INHERIT_SEED_STREAM_TOKEN,
    ResearchIntervention,
    ResearchInterventionKind,
    intervention_fingerprint,
    seed_stream_token_for_intervention,
)
from simulation.identifiers import derive_branch_id, derive_branch_run_id, derive_run_id
from simulation.models import RunId, SimulationRunConfig, StochasticIdentity
from simulation.runner_models import MemoryMode
from world.models import PhysicalRules


def _fingerprint() -> str:
    intervention = ResearchIntervention(
        kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
        agent_ids=("agent-a",),
        memory_mode=MemoryMode.REFERENCE,
    )
    return intervention_fingerprint(intervention)


def test_branch_run_id_stable_and_distinct_from_seed_run() -> None:
    fingerprint = _fingerprint()
    parent = RunId("parent-run-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    left = derive_branch_run_id(parent, 7, fingerprint, INHERIT_SEED_STREAM_TOKEN)
    right = derive_branch_run_id(parent, 7, fingerprint, INHERIT_SEED_STREAM_TOKEN)
    assert left == right
    assert left.value == right.value

    seed_run = derive_run_id(
        SimulationRunConfig(
            seed=7,
            physical_rules=PhysicalRules(),
            stochastic_identity=StochasticIdentity("shared-stream"),
            derivation_version="v3",
        )
    )
    assert left != seed_run


def test_branch_id_distinct_from_child_run_id() -> None:
    fingerprint = _fingerprint()
    parent = "parent-run"
    child = derive_branch_run_id(parent, 3, fingerprint, INHERIT_SEED_STREAM_TOKEN)
    branch = derive_branch_id(parent, 3, fingerprint, INHERIT_SEED_STREAM_TOKEN)
    assert child.value != branch


def test_alternate_seed_stream_changes_identity() -> None:
    fingerprint = intervention_fingerprint(
        ResearchIntervention(
            kind=ResearchInterventionKind.ALTERNATE_SEED_STREAM,
            alternate_stochastic_identity=StochasticIdentity("alt-a"),
        )
    )
    token = seed_stream_token_for_intervention(
        ResearchIntervention(
            kind=ResearchInterventionKind.ALTERNATE_SEED_STREAM,
            alternate_stochastic_identity=StochasticIdentity("alt-a"),
        )
    )
    inherit = derive_branch_run_id("parent", 1, fingerprint, INHERIT_SEED_STREAM_TOKEN)
    alternate = derive_branch_run_id("parent", 1, fingerprint, token)
    assert inherit != alternate
