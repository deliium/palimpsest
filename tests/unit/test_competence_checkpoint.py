"""The competence model is an optional runtime checkpoint field."""

from __future__ import annotations

from agents.cognition.competence import (
    CompetenceDomain,
    default_competence_belief_policy,
    empty_competence_model,
    update_competence,
)
from simulation.run_control import AgentRuntimeCheckpoint
from tests.unit.test_competence_update import _observation, _search
from tests.unit.test_identity_runtime import _runtime


def test_checkpoint_copies_competence_like_reputation() -> None:
    runtime, _reader = _runtime()
    assert runtime._competence is None
    model = update_competence(
        empty_competence_model(runtime.agent_id),
        _observation(_search("evt-hit", success=True)),
        (),
        default_competence_belief_policy(),
    )
    runtime._competence = model
    exported = runtime.export_runtime_checkpoint()
    assert type(exported) is AgentRuntimeCheckpoint
    assert exported.competence_model == model
    fresh, _reader = _runtime()
    fresh.restore_runtime_checkpoint(exported)
    restored = fresh._competence
    assert restored is not None
    assert restored.owner_id == runtime.agent_id
    assert restored.belief_for(CompetenceDomain.FORAGING).support_mass == 0.10
    blank = AgentRuntimeCheckpoint(
        agent_id=runtime.agent_id,
        status=exported.status,
        internal_state=exported.internal_state,
        last_observation_key=None,
        processed_invocation_count=0,
        finalized_hash_count=0,
        goals=runtime.agent.goals,
    )
    assert blank.competence_model is None
    runtime.restore_runtime_checkpoint(blank)
    assert runtime._competence is None
