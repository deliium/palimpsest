"""Symbolic ledgers carry through checkpoints and never into blank slates."""

from __future__ import annotations

import pytest

from agents.cognition.semantic_naming import NamingReferentKind
from agents.cognition.symbolic_language import (
    SymbolicComposition,
    SymbolicCompositionKind,
    SymbolicLedger,
    SymbolicReferentHypothesis,
    SymbolicStatus,
    composition_id,
)
from agents.models import AgentId


def _ledger(owner: AgentId) -> SymbolicLedger:
    composition = SymbolicComposition(
        composition_id=composition_id(
            owner, SymbolicCompositionKind.ATTRIBUTIVE, ("alpha", "beta")
        ),
        owner_id=owner,
        kind=SymbolicCompositionKind.ATTRIBUTIVE,
        parts=("alpha", "beta"),
        referent_hypothesis=SymbolicReferentHypothesis(
            NamingReferentKind.LOCATION, 0.3
        ),
        status=SymbolicStatus.ACTIVE,
        strength=0.5,
        evidence_count=3,
        first_tick=1,
        last_tick=3,
    )
    return SymbolicLedger(owner_id=owner, compositions=(composition,))


def test_blank_slate_excludes_symbolic_fields() -> None:
    import simulation.new_agent_initialization as module

    names: set[str] = set()
    for value in vars(module).values():
        if isinstance(value, (set, frozenset, tuple)):
            names.update(item for item in value if isinstance(item, str))
    assert "symbolic_language" in names
    assert "symbolic_ledger" in names


def test_checkpoint_round_trips_enabled_ledger() -> None:
    from agents.cognition.models import InternalAgentState
    from simulation.agent_runtime import AgentRuntimeStatus
    from simulation.run_control import AgentRuntimeCheckpoint

    owner = AgentId("a")
    checkpoint = AgentRuntimeCheckpoint(
        agent_id=owner,
        status=AgentRuntimeStatus.ACTIVE,
        internal_state=InternalAgentState(owner_id=owner),
        last_observation_key=None,
        processed_invocation_count=0,
        finalized_hash_count=0,
        goals=(),
        symbolic_language=_ledger(owner),
    )
    assert checkpoint.symbolic_language == _ledger(owner)


def test_foreign_symbolic_ledger_rejected_by_checkpoint() -> None:
    from agents.cognition.models import InternalAgentState
    from simulation.agent_runtime import AgentRuntimeStatus
    from simulation.run_control import AgentRuntimeCheckpoint

    with pytest.raises(ValueError):
        AgentRuntimeCheckpoint(
            agent_id=AgentId("a"),
            status=AgentRuntimeStatus.ACTIVE,
            internal_state=InternalAgentState(owner_id=AgentId("a")),
            last_observation_key=None,
            processed_invocation_count=0,
            finalized_hash_count=0,
            goals=(),
            symbolic_language=_ledger(AgentId("b")),
        )
