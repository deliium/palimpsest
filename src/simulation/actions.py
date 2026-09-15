"""Simulation-owned admission from agent commands to bound requests.

Only this path binds authenticated agent identity and world/revision context.
Commands and proposals remain non-authoritative.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from agents.contracts import IdentityTranslator
from agents.models import AgentId
from simulation.clock import Tick, require_exact_nonneg_int
from simulation.identifiers import (
    derive_event_id,
    derive_proposal_id,
    derive_request_id,
)
from simulation.models import RunId, SimulationRunConfig
from simulation.randomness import StreamScope
from world.actions import (
    ActionProposal,
    ActionRequest,
    AgentCommand,
    require_agent_command,
)
from world.identifiers import EventId, WorldId, WorldRevision

__all__ = [
    "admit_agent_command",
    "canonical_admission_keys",
    "canonical_event_keys",
    "derive_engine_event_id",
    "future_effect_scope",
]


def canonical_admission_keys(
    *,
    run_id: RunId,
    world_id: WorldId,
    tick: Tick,
    ordinal: int,
    agent_id: AgentId,
) -> tuple[str, ...]:
    """Engine-owned canonical keys for proposal/request derivation."""
    if type(run_id) is not RunId:
        raise TypeError("canonical_admission_keys requires RunId")
    if type(world_id) is not WorldId:
        raise TypeError("canonical_admission_keys requires WorldId")
    if type(tick) is not Tick:
        raise TypeError("canonical_admission_keys requires Tick")
    if type(agent_id) is not AgentId:
        raise TypeError("canonical_admission_keys requires AgentId")
    ordinal_value = require_exact_nonneg_int("ordinal", ordinal)
    return (
        "engine",
        run_id.value,
        world_id.value,
        f"tick:{tick.value}",
        f"ordinal:{ordinal_value}",
        f"agent:{agent_id.value}",
    )


def canonical_event_keys(
    *,
    run_id: RunId,
    world_id: WorldId,
    tick: Tick,
    ordinal: int,
    agent_id: AgentId,
    sequence: int,
) -> tuple[str, ...]:
    """Engine-owned canonical keys for objective event derivation."""
    sequence_value = require_exact_nonneg_int("sequence", sequence)
    return (
        *canonical_admission_keys(
            run_id=run_id,
            world_id=world_id,
            tick=tick,
            ordinal=ordinal,
            agent_id=agent_id,
        ),
        f"event:{sequence_value}",
    )


def derive_engine_event_id(
    config: SimulationRunConfig,
    *,
    run_id: RunId,
    world_id: WorldId,
    tick: Tick,
    ordinal: int,
    agent_id: AgentId,
    sequence: int,
) -> EventId:
    return derive_event_id(
        config,
        *canonical_event_keys(
            run_id=run_id,
            world_id=world_id,
            tick=tick,
            ordinal=ordinal,
            agent_id=agent_id,
            sequence=sequence,
        ),
    )


def future_effect_scope(
    *,
    run_id: RunId,
    world_id: WorldId,
    tick: Tick,
    ordinal: int,
    agent_id: AgentId,
    purpose: str,
) -> StreamScope:
    """Canonical future random-effect scope. V1 performs no draws from it."""
    if type(run_id) is not RunId:
        raise TypeError("future_effect_scope requires RunId")
    if type(world_id) is not WorldId:
        raise TypeError("future_effect_scope requires WorldId")
    if type(tick) is not Tick:
        raise TypeError("future_effect_scope requires Tick")
    if type(agent_id) is not AgentId:
        raise TypeError("future_effect_scope requires AgentId")
    if type(purpose) is not str or not purpose:
        raise ValueError("purpose must be a non-empty str")
    ordinal_value = require_exact_nonneg_int("ordinal", ordinal)
    return StreamScope(
        namespace="effect",
        names=(
            run_id.value,
            world_id.value,
            f"tick:{tick.value}",
            f"ordinal:{ordinal_value}",
            f"agent:{agent_id.value}",
            purpose,
        ),
    )


def admit_agent_command(
    *,
    config: SimulationRunConfig,
    agent_id: AgentId,
    command: object,
    translator: IdentityTranslator,
    world_id: WorldId,
    revision: WorldRevision,
    keys: Sequence[str],
) -> tuple[ActionProposal, ActionRequest]:
    """Admit an exact command under authenticated agent context.

    Allocates deterministic proposal/request IDs, translates the agent to a
    world entity, and returns a non-authoritative bound request. Callers cannot
    supply actor IDs or operational request metadata. Engine callers should pass
    :func:`canonical_admission_keys` rather than ad-hoc keys.
    """
    if type(config) is not SimulationRunConfig:
        raise TypeError("admit_agent_command requires SimulationRunConfig")
    if type(agent_id) is not AgentId:
        raise TypeError("admit_agent_command requires authenticated AgentId")
    if type(world_id) is not WorldId:
        raise TypeError("admit_agent_command requires WorldId")
    if type(revision) is not WorldRevision:
        raise TypeError("admit_agent_command requires WorldRevision")
    if isinstance(command, Mapping):
        raise TypeError("raw mappings cannot be admitted as agent commands")
    typed_command: AgentCommand = require_agent_command(command)
    actor_id = translator.to_entity_id(agent_id)
    round_trip = translator.to_agent_id(actor_id)
    if round_trip != agent_id:
        raise ValueError("identity translation mismatch for admitted agent")
    key_tuple = tuple(keys)
    if not key_tuple:
        raise ValueError("admission requires at least one canonical key")
    for key in key_tuple:
        if not isinstance(key, str) or key == "":
            raise ValueError("admission keys must be non-empty strings")
    proposal_id = derive_proposal_id(config, "admit", *key_tuple)
    request_id = derive_request_id(config, "admit", *key_tuple)
    proposal = ActionProposal(proposal_id=proposal_id, command=typed_command)
    request = ActionRequest(
        request_id=request_id,
        proposal_id=proposal_id,
        world_id=world_id,
        actor_id=actor_id,
        revision=revision,
        command=typed_command,
    )
    return proposal, request
