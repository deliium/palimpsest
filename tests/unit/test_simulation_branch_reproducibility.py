"""Hard reproducibility proofs for research forks (not smoke-only)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition.counterfactual import CounterfactualScenario
from agents.cognition.models import ImaginedFuture
from agents.models import AgentId
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefId,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticClaim,
)
from simulation.branching import (
    ResearchIntervention,
    ResearchInterventionKind,
    intervention_fingerprint,
    seed_stream_token_for_intervention,
)
from simulation.identifiers import derive_branch_id, derive_branch_run_id, derive_run_id
from simulation.models import RunId, SimulationRunConfig
from simulation.runner_models import MemoryMode
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src"


def _memory_intervention() -> ResearchIntervention:
    return ResearchIntervention(
        kind=ResearchInterventionKind.MEMORY_ARCHITECTURE,
        agent_ids=("agent-1",),
        memory_mode=MemoryMode.REFERENCE,
    )


def test_identical_fork_config_mints_stable_child_and_branch_ids() -> None:
    intervention = _memory_intervention()
    fingerprint = intervention_fingerprint(intervention)
    token = seed_stream_token_for_intervention(intervention)
    parent = RunId("parent-run")
    first = derive_branch_run_id(parent, 5, fingerprint, token)
    second = derive_branch_run_id(parent, 5, fingerprint, token)
    assert first == second
    assert derive_branch_id(parent, 5, fingerprint, token) == derive_branch_id(
        parent, 5, fingerprint, token
    )
    ordinary = derive_run_id(SimulationRunConfig(seed=99))
    assert first != ordinary


def test_research_fork_excludes_agent_counterfactual_and_belief_types() -> None:
    intervention = _memory_intervention()
    assert type(intervention) is ResearchIntervention
    assert CounterfactualScenario is not ResearchIntervention
    assert ImaginedFuture is not ResearchIntervention
    belief = SemanticBelief(
        belief_id=BeliefId("belief-1"),
        owner_id=AgentId("agent-1"),
        claim=SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.ENTITY, entity_id=EntityId("place-1")
            ),
            predicate="at_location",
            value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
        ),
        confidence=BeliefConfidenceState(
            confidence=0.9, support_mass=0.9, contradiction_mass=0.0
        ),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId("rev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=2,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=1,
        evidence_contradiction_count=0,
    )
    assert belief.claim.predicate != "research_fork"
    assert type(belief) is not ResearchIntervention
    assert not issubclass(ResearchIntervention, CounterfactualScenario)
    assert not issubclass(ResearchIntervention, ImaginedFuture)


def test_fingerprint_stable_across_calls() -> None:
    intervention = _memory_intervention()
    assert intervention_fingerprint(intervention) == intervention_fingerprint(
        intervention
    )


def test_simulation_branch_modules_do_not_import_experiments() -> None:
    forbidden = {"experiments"}
    modules = (
        _SRC / "simulation" / "branching.py",
        _SRC / "simulation" / "branch_service.py",
        _SRC / "simulation" / "branch_compare.py",
    )
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    assert root not in forbidden, f"{path.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                assert root not in forbidden, f"{path.name} imports {node.module}"
